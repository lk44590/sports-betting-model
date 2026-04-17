"""
Neural Network Ensemble for Sports Betting Model.
Deep learning model using TensorFlow/Keras.
Works alongside RF and GB models as part of ensemble.
"""

import numpy as np
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

# Try to import TensorFlow, use mock if not available
try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models, callbacks
    from tensorflow.keras.optimizers import Adam
    TF_AVAILABLE = True
except ImportError:
    print("TensorFlow not available. Using mock implementation.")
    TF_AVAILABLE = False
    # Mock classes for when TF is not installed
    class MockModel:
        def predict(self, X):
            return np.array([[0.5]] * len(X))
    tf = None

# Model storage path
MODELS_PATH = Path(__file__).parent.parent.parent / "data" / "models"
MODELS_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class ModelPrediction:
    """Prediction result from neural network."""
    probability: float
    confidence: float
    model_version: str


class NeuralEnsemble:
    """
    Neural Network ensemble for sports betting prediction.
    Uses deep learning to predict win probabilities.
    """
    
    def __init__(self, input_dim: int = 15):
        self.input_dim = input_dim
        self.model = None
        self.scaler_mean = None
        self.scaler_std = None
        self.training_history = []
        self.model_version = "1.0.0"
        
        # Try to load existing model
        self._load_model()
    
    def _build_model(self) -> Any:
        """Build neural network architecture."""
        if not TF_AVAILABLE:
            print("TensorFlow not available, returning mock model")
            return MockModel()
        
        model = keras.Sequential([
            # Input layer
            layers.Input(shape=(self.input_dim,)),
            
            # Hidden layers with dropout for regularization
            layers.Dense(128, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.3),
            
            layers.Dense(64, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.2),
            
            layers.Dense(32, activation='relu'),
            layers.BatchNormalization(),
            layers.Dropout(0.2),
            
            # Output layer (probability)
            layers.Dense(1, activation='sigmoid')
        ])
        
        # Compile with appropriate loss and optimizer
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss='binary_crossentropy',
            metrics=['accuracy', 'AUC']
        )
        
        return model
    
    def _load_model(self) -> bool:
        """Load trained model from disk."""
        model_file = MODELS_PATH / "neural_ensemble.keras"
        scaler_file = MODELS_PATH / "neural_scaler.json"
        
        if not TF_AVAILABLE:
            self.model = MockModel()
            return False
        
        try:
            if model_file.exists():
                self.model = keras.models.load_model(model_file)
                print(f"Loaded neural ensemble from {model_file}")
                
                # Load scaler params
                if scaler_file.exists():
                    with open(scaler_file, 'r') as f:
                        scaler_data = json.load(f)
                        self.scaler_mean = np.array(scaler_data['mean'])
                        self.scaler_std = np.array(scaler_data['std'])
                
                return True
        except Exception as e:
            print(f"Error loading model: {e}")
        
        # Build new model if loading failed
        self.model = self._build_model()
        return False
    
    def _save_model(self) -> None:
        """Save trained model to disk."""
        if not TF_AVAILABLE or self.model is None:
            return
        
        try:
            model_file = MODELS_PATH / "neural_ensemble.keras"
            self.model.save(model_file)
            
            # Save scaler params
            if self.scaler_mean is not None and self.scaler_std is not None:
                scaler_file = MODELS_PATH / "neural_scaler.json"
                with open(scaler_file, 'w') as f:
                    json.dump({
                        'mean': self.scaler_mean.tolist(),
                        'std': self.scaler_std.tolist()
                    }, f)
            
            print(f"Saved neural ensemble to {model_file}")
        except Exception as e:
            print(f"Error saving model: {e}")
    
    def _normalize_features(self, X: np.ndarray) -> np.ndarray:
        """Normalize features for neural network."""
        if self.scaler_mean is None or self.scaler_std is None:
            # First time - compute from data
            self.scaler_mean = np.mean(X, axis=0)
            self.scaler_std = np.std(X, axis=0) + 1e-8  # Avoid division by zero
        
        return (X - self.scaler_mean) / self.scaler_std
    
    def extract_features(self, candidate: Dict[str, Any]) -> np.ndarray:
        """
        Extract features from candidate for neural network.
        Creates feature vector from bet characteristics.
        """
        features = []
        
        # 1. Implied probability from odds
        odds = candidate.get('odds', -110)
        if odds > 0:
            implied_prob = 100 / (odds + 100)
        else:
            implied_prob = abs(odds) / (abs(odds) + 100)
        features.append(implied_prob)
        
        # 2. Model probability estimate
        features.append(candidate.get('model_probability', 0.5))
        
        # 3. Data quality
        features.append(candidate.get('data_quality', 75) / 100)
        
        # 4. Sample size (normalized)
        features.append(min(candidate.get('sample_size', 30) / 82, 1.0))
        
        # 5. Sport encoding (one-hot-ish representation)
        sport = candidate.get('sport', 'NBA')
        sport_features = self._encode_sport(sport)
        features.extend(sport_features)
        
        # 6. Market type
        market = candidate.get('market_type', 'moneyline')
        market_features = self._encode_market(market)
        features.extend(market_features)
        
        # 7. Time features (hour of day, day of week)
        from datetime import datetime
        now = datetime.now()
        features.append(now.hour / 24)
        features.append(now.weekday() / 7)
        
        # 8. Historical performance features (if available)
        # These would come from the database
        sport_win_rate = self._get_sport_win_rate(sport)
        features.append(sport_win_rate)
        
        # Pad or trim to ensure correct dimension
        while len(features) < self.input_dim:
            features.append(0.0)
        features = features[:self.input_dim]
        
        return np.array(features)
    
    def _encode_sport(self, sport: str) -> List[float]:
        """One-hot encode sport."""
        sports = ['NBA', 'NFL', 'MLB', 'NHL', 'NCAAMB', 'NCAAF', 'NCAABASE', 'WNBA']
        encoding = [1.0 if s == sport else 0.0 for s in sports]
        return encoding[:3]  # Take first 3 to keep dimension reasonable
    
    def _encode_market(self, market: str) -> List[float]:
        """One-hot encode market type."""
        markets = ['moneyline', 'spread', 'total', 'team_total', 'player_prop']
        encoding = [1.0 if m == market else 0.0 for m in markets]
        return encoding[:2]  # Take first 2
    
    def _get_sport_win_rate(self, sport: str) -> float:
        """Get historical win rate for sport (placeholder)."""
        # This would query the database
        # For now return neutral 0.5
        return 0.5
    
    def predict(self, candidate: Dict[str, Any]) -> Optional[ModelPrediction]:
        """
        Make prediction for a candidate.
        """
        try:
            # Extract features
            features = self.extract_features(candidate)
            X = features.reshape(1, -1)
            
            # Normalize
            X_normalized = self._normalize_features(X)
            
            # Predict
            prediction = self.model.predict(X_normalized, verbose=0)[0][0]
            
            # Calculate confidence based on prediction distance from 0.5
            confidence = abs(prediction - 0.5) * 2  # 0 to 1
            
            return ModelPrediction(
                probability=float(prediction),
                confidence=float(confidence),
                model_version=self.model_version
            )
        except Exception as e:
            print(f"Prediction error: {e}")
            return None
    
    def predict_batch(self, candidates: List[Dict[str, Any]]) -> List[Optional[ModelPrediction]]:
        """Predict for multiple candidates."""
        if not candidates:
            return []
        
        try:
            # Extract features for all
            features_list = [self.extract_features(c) for c in candidates]
            X = np.array(features_list)
            
            # Normalize
            X_normalized = self._normalize_features(X)
            
            # Batch predict
            predictions = self.model.predict(X_normalized, verbose=0)
            
            results = []
            for pred in predictions:
                prob = pred[0]
                confidence = abs(prob - 0.5) * 2
                results.append(ModelPrediction(
                    probability=float(prob),
                    confidence=float(confidence),
                    model_version=self.model_version
                ))
            
            return results
        except Exception as e:
            print(f"Batch prediction error: {e}")
            return [None] * len(candidates)
    
    def train(self, 
             candidates: List[Dict[str, Any]], 
             results: List[int],
             epochs: int = 50,
             validation_split: float = 0.2) -> Dict[str, Any]:
        """
        Train the neural network on historical data.
        
        Args:
            candidates: List of candidate features
            results: List of outcomes (1 for win, 0 for loss)
            epochs: Training epochs
            validation_split: Fraction for validation
        """
        if not TF_AVAILABLE:
            return {"success": False, "error": "TensorFlow not available"}
        
        if len(candidates) < 50:
            return {"success": False, "error": "Need at least 50 samples to train"}
        
        try:
            # Prepare data
            X = np.array([self.extract_features(c) for c in candidates])
            y = np.array(results)
            
            # Normalize
            X_normalized = self._normalize_features(X)
            
            # Split
            split_idx = int(len(X) * (1 - validation_split))
            X_train, X_val = X_normalized[:split_idx], X_normalized[split_idx:]
            y_train, y_val = y[:split_idx], y[split_idx:]
            
            # Callbacks
            early_stop = callbacks.EarlyStopping(
                monitor='val_loss',
                patience=10,
                restore_best_weights=True
            )
            
            reduce_lr = callbacks.ReduceLROnPlateau(
                monitor='val_loss',
                factor=0.5,
                patience=5,
                min_lr=0.00001
            )
            
            # Train
            history = self.model.fit(
                X_train, y_train,
                validation_data=(X_val, y_val),
                epochs=epochs,
                batch_size=32,
                callbacks=[early_stop, reduce_lr],
                verbose=1
            )
            
            # Evaluate
            val_loss, val_acc, val_auc = self.model.evaluate(X_val, y_val, verbose=0)
            
            # Save
            self._save_model()
            
            return {
                "success": True,
                "epochs_trained": len(history.history['loss']),
                "final_val_loss": float(val_loss),
                "final_val_accuracy": float(val_acc),
                "final_val_auc": float(val_auc),
                "training_samples": len(X_train),
                "validation_samples": len(X_val)
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the neural model."""
        info = {
            "model_version": self.model_version,
            "input_dim": self.input_dim,
            "tensorflow_available": TF_AVAILABLE,
            "model_loaded": self.model is not None,
            "scaler_configured": self.scaler_mean is not None
        }
        
        if TF_AVAILABLE and self.model:
            info["model_summary"] = str(self.model.summary())
        
        return info


# Global instance
neural_ensemble = NeuralEnsemble()


def test_neural_ensemble():
    """Test the neural ensemble."""
    print("Testing Neural Ensemble")
    print("=" * 60)
    
    # Check model info
    info = neural_ensemble.get_model_info()
    print(f"TensorFlow Available: {info['tensorflow_available']}")
    print(f"Model Loaded: {info['model_loaded']}")
    print(f"Input Dimension: {info['input_dim']}")
    
    # Test prediction
    test_candidate = {
        "bet_id": "test-001",
        "sport": "NBA",
        "odds": -110,
        "model_probability": 0.55,
        "data_quality": 85,
        "sample_size": 35,
        "market_type": "moneyline"
    }
    
    print("\nTesting prediction...")
    prediction = neural_ensemble.predict(test_candidate)
    
    if prediction:
        print(f"Predicted Probability: {prediction.probability:.3f}")
        print(f"Confidence: {prediction.confidence:.3f}")
        print(f"Model Version: {prediction.model_version}")
    else:
        print("Prediction failed")
    
    print("\nTo train the model, provide historical data with outcomes.")
    print("The model will learn from past bets to improve predictions.")


if __name__ == "__main__":
    test_neural_ensemble()
