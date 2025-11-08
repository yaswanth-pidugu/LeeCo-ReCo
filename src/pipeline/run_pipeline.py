from src.pipeline.scraper import scrape_latest_data
from src.pipeline.preprocess import preprocess_data
from src.database.db_insert import insert_problems_from_csv
from src.modeling.train import train_and_save_model


def run_pipeline():
    print("Starting LeetCode Automation Pipeline")

    raw_path = "data/raw/leetcode_latest.csv"
    processed_path = "data/processed/preprocessed_data.csv"
    model_path = "models/lightgbm_model.pkl"

    # 1. Scrape latest data
    print("Scraping latest LeetCode data...")
    scrape_latest_data(save_path=raw_path)

    # 2. Preprocess & feature engineering
    print("Preprocessing and cleaning...")
    preprocess_data(raw_path, processed_path)

    # 3. Train and save model
    print("Training ML model...")
    train_and_save_model(processed_path, model_path)

    # 4. Update MySQL DB
    print("Updating database with latest records...")
    insert_problems_from_csv(processed_path)

    print("Pipeline Completed Successfully")


if __name__ == "__main__":
    run_pipeline()