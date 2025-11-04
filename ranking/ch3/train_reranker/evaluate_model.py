#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd
import lightgbm as lgb

def main(test_csv, model_file):
    print(f"Loading test data from {test_csv}...")
    df = pd.read_csv(test_csv)
    
    print(f"Loading model from {model_file}...")
    # Load native LightGBM model
    model = lgb.Booster(model_file=model_file)
    
    # Prepare features (same order as training)
    feature_cols = [
        'Price', 'AverageRating', 'closeness_description', 'closeness_productname',
        'native_rank_description', 'native_rank_name'
    ]
    
    X = df[feature_cols]
    y_true = df['relevance_label'].values
    
    # Make predictions
    print("Making predictions...")
    y_pred = model.predict(X)
    
    # Calculate metrics
    rmse = np.sqrt(np.mean((y_pred - y_true) ** 2))
    mae = np.mean(np.abs(y_pred - y_true))
    
    print("\n" + "=" * 60)
    print(f"{'Test Results':^60}")
    print("=" * 60)
    print(f"Total predictions: {len(y_pred)}")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE:  {mae:.4f}")
    print("=" * 60)
    
    # Print some example predictions
    print("\nSample predictions (first 10):")
    print(f"{'Predicted':<12} {'Actual':<12} {'Error':<12}")
    print("-" * 36)
    for i in range(min(10, len(y_pred))):
        error = y_pred[i] - y_true[i]
        print(f"{y_pred[i]:<12.4f} {y_true[i]:<12} {error:<12.4f}")
    
    # Print distribution of predictions vs actuals
    print("\nPrediction distribution:")
    print(f"Mean prediction: {np.mean(y_pred):.4f}")
    print(f"Mean actual: {np.mean(y_true):.4f}")
    print(f"Std prediction: {np.std(y_pred):.4f}")
    print(f"Std actual: {np.std(y_true):.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate trained LightGBM model on test data."
    )
    parser.add_argument(
        "--test_csv",
        type=str,
        default="test_data.csv",
        help="Path to test CSV file (default: test_data.csv)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="lightgbm_model.txt",
        help="Path to trained model file (default: lightgbm_model.txt)"
    )
    
    args = parser.parse_args()
    main(args.test_csv, args.model)

