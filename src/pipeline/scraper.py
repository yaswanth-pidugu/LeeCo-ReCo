import requests
import json
import time
import random
import pandas as pd
import os
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


GRAPHQL_URL = "https://leetcode.com/graphql/"
HOMEPAGE = "https://leetcode.com/problemset/"


def make_leetcode_session():
    s = requests.Session()
    retry = Retry(
        total=5, connect=5, read=5,
        backoff_factor=1.2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    r = s.get(HOMEPAGE, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://leetcode.com/",
        "Origin": "https://leetcode.com",
        "Accept": "application/json, text/plain, */*",
    }, timeout=(10, 30))
    csrftoken = s.cookies.get("csrftoken", "")
    s.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://leetcode.com/",
        "Origin": "https://leetcode.com",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "x-csrftoken": csrftoken,
    })
    return s


PROBLEMSET_QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(categorySlug: $categorySlug, limit: $limit, skip: $skip, filters: $filters) {
    total: totalNum
    questions: data {
      questionFrontendId
      title
      titleSlug
      difficulty
      acRate
      isPaidOnly
      topicTags { name slug }
    }
  }
}
"""

QUESTION_DETAIL_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    questionFrontendId
    title
    titleSlug
    difficulty
    isPaidOnly
    acRate
    content
    stats
    likes
    dislikes
    topicTags { name slug }
    similarQuestions
    discussionCount
  }
}
"""


def graphql_query(session, query, variables=None, max_retries=4):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            r = session.post(GRAPHQL_URL, json=payload, timeout=(10, 60))
            js = r.json()
        except Exception as e:
            last_err = e
            time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.6))
            continue

        if "errors" in js:
            last_err = RuntimeError(js["errors"][0].get("message", "GraphQL error"))
            time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.6))
            continue

        if "data" in js:
            return js["data"]

        last_err = RuntimeError(f"Unexpected response: {r.status_code} {r.text[:300]}")
        time.sleep((2 ** (attempt - 1)) + random.uniform(0, 0.6))
    raise last_err or RuntimeError("GraphQL request failed")


def fetch_all_problems_df(page_size=50, checkpoint_path=None):
    session = make_leetcode_session()
    all_rows = []
    skip = 0
    total = None
    seen = set()

    if checkpoint_path and os.path.exists(checkpoint_path):
        old_df = pd.read_csv(checkpoint_path)
        seen = set(old_df['titleSlug'])
        all_rows = old_df.to_dict('records')
        print(f"Loaded {len(seen)} existing problems from checkpoint.")

    while True:
        variables = {"categorySlug": "", "limit": page_size, "skip": skip, "filters": {}}
        data = graphql_query(session, PROBLEMSET_QUERY, variables)
        root = data["problemsetQuestionList"]
        if total is None:
            total = root["total"] or 0
        batch = root["questions"] or []
        if not batch:
            break

        for q in batch:
            slug = q["titleSlug"]
            if slug in seen:
                continue

            try:
                detail_data = graphql_query(session, QUESTION_DETAIL_QUERY, {"titleSlug": slug})
                qd = detail_data["question"]

                stats = json.loads(qd.get("stats", "{}"))
                similar = json.loads(qd.get("similarQuestions", "[]"))

                row = {
                    "frontend_id": qd.get("questionFrontendId"),
                    "internal_id": qd.get("questionId"),
                    "title": qd.get("title"),
                    "titleSlug": slug,
                    "difficulty": qd.get("difficulty"),
                    "is_premium": qd.get("isPaidOnly"),
                    "topic_tags": [t["name"] for t in qd.get("topicTags", [])],
                    "similar_questions": [s.get("title") for s in similar] if similar else [],
                    "no_similar_questions": len(similar),
                    "acceptance": qd.get("acRate"),
                    "accepted": stats.get("totalAcceptedRaw"),
                    "submission": stats.get("totalSubmissionRaw"),
                    "discussion_count": qd.get("discussionCount"),
                    "likes": qd.get("likes"),
                    "dislikes": qd.get("dislikes"),
                    "description": qd.get("content", ""),
                    "problem_URL": f"https://leetcode.com/problems/{slug}/",
                    "solution_URL": f"https://leetcode.com/problems/{slug}/solution/" if not qd.get("isPaidOnly") else None,
                    "last_updated": datetime.now().strftime("%Y-%m-%d")
                }

                all_rows.append(row)
                seen.add(slug)

            except Exception as e:
                print(f"Error fetching {slug}: {e}")
                continue

        if checkpoint_path:
            pd.DataFrame(all_rows).to_csv(checkpoint_path, index=False)

        skip += page_size
        if len(seen) >= total:
            break
        time.sleep(random.uniform(0.8, 1.5))

    return pd.DataFrame(all_rows)


def scrape_latest_data(save_path="data/raw/leetcode_latest.csv"):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    df = fetch_all_problems_df(page_size=50, checkpoint_path=save_path)
    df.to_csv(save_path, index=False)
    print(f"Scraping complete — {len(df)} problems saved to {save_path}")