import os
import pandas as pd
import numpy as np
from flask import render_template, Flask, request, jsonify
from sklearn.impute import KNNImputer
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
from catboost import CatBoostRegressor
from werkzeug.utils import secure_filename

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

models = {}
metrics = {}

def preprocess_dataset(df):
    for index, row in df.iterrows():
        try:
            pd.to_datetime(row["Date"])
        except Exception:
            df.at[index, "Infrastructure_Machineries"] = row["Date"]
            df.at[index, "Date"] = np.nan

    df["Infrastructure_Machineries"].replace("invalid_data", np.nan, inplace=True)

    mapping = {val: idx for idx, val in enumerate(df["Infrastructure_Machineries"].dropna().unique())}
    df["Infra_Machinery_Encoded"] = df["Infrastructure_Machineries"].map(mapping)

    imputer = KNNImputer(n_neighbors=3)
    df["Infra_Machinery_Encoded"] = imputer.fit_transform(df[["Infra_Machinery_Encoded"]])

    reverse_mapping = {v: k for k, v in mapping.items()}
    df["Infrastructure_Machineries"] = df["Infra_Machinery_Encoded"].round().map(reverse_mapping)
    df.drop(columns=["Infra_Machinery_Encoded"], inplace=True)

    df["Market_Share"] = df["Market_Share"].replace(35000, 35)
    df = df[df['Daily_Sales_Quantity'] > 0]

    return df

def train_models(df):
    global models, metrics
    categories = df['Infrastructure_Machineries'].unique()
    for cat in categories:
        subset = df[df['Infrastructure_Machineries'] == cat].copy()
        drop_cols = ['Unnamed: 0', 'Un_Named', 'Date', 'Customer_Id', 'Region', 'Infrastructure_Machineries']
        subset.drop(columns=[col for col in drop_cols if col in subset.columns], inplace=True)

        X = subset.drop(columns=["Daily_Sales_Quantity"])
        y = subset["Daily_Sales_Quantity"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        model = CatBoostRegressor(n_estimators=200, learning_rate=0.05, verbose=0)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        models[cat] = model
        metrics[cat] = {
            "RMSE": float(np.sqrt(mean_squared_error(y_test, y_pred))),
            "MSE": float(mean_squared_error(y_test, y_pred)),
            "R2": float(r2_score(y_test, y_pred))
        }

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/upload', methods=['POST'])
def upload():
    train_file = request.files['train']
    filename = secure_filename(train_file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    train_file.save(path)

    df = pd.read_csv(path)
    df = preprocess_dataset(df)
    train_models(df)

    return jsonify({"message": "Training completed", "models": list(models.keys())})

@app.route('/predict', methods=['POST'])
def predict():
    input_file = request.files['input']
    filename = secure_filename(input_file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    input_file.save(path)
    df = pd.read_csv(path)

    predictions = []
    named_predictions = []

    for index, row in df.iterrows():
        cat = row['Infrastructure_Machineries']
        model = models.get(cat)
        if model:
            try:
                input_data = row.drop(["Date", "Customer_Id", "Region", "Infrastructure_Machineries"]).values.reshape(1, -1)
                pred = model.predict(input_data)[0]
                predictions.append(pred)
                named_predictions.append({"name": cat, "value": pred})
            except Exception:
                predictions.append(None)
                named_predictions.append({"name": cat, "value": None})
        else:
            predictions.append(None)
            named_predictions.append({"name": cat, "value": None})

    df['Predicted_Sales'] = predictions
    df.to_csv(os.path.join(UPLOAD_FOLDER, "predicted_output.csv"), index=False)

    return jsonify({"predictions": predictions, "named_predictions": named_predictions})

@app.route('/optimize', methods=['POST'])
def optimize():
    inventory_size = int(request.form['inventory'])
    df = pd.read_csv(os.path.join(UPLOAD_FOLDER, "predicted_output.csv"))

    total_sales = df['Predicted_Sales'].sum()
    df['Optimized_Inventory'] = (df['Predicted_Sales'] / total_sales) * inventory_size
    df['Optimized_Inventory'] = df['Optimized_Inventory'].round()

    before = df['Predicted_Sales'].sum()
    after = df['Optimized_Inventory'].sum()

    inventory_changes = df[['Infrastructure_Machineries', 'Predicted_Sales', 'Optimized_Inventory']].copy()
    inventory_changes['Change'] = inventory_changes['Optimized_Inventory'] - inventory_changes['Predicted_Sales']

    return jsonify({
        "before_optimization": before,
        "after_optimization": after,
        "metrics": metrics,
        "summary": f"Optimized inventory sum: {after}, originally predicted: {before}",
        "inventory_changes": inventory_changes.to_dict(orient="records")
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
