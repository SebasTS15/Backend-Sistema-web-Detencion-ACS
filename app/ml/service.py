from pathlib import Path
from typing import Any

import torch
from torch import nn

from app.core.config import get_settings
from app.ml.model import ResNetApneaCentral
from app.ml.preprocessing import prepare_signal


class ModelService:
    def __init__(self, model_path: Path, threshold: float) -> None:
        self.model_path = model_path
        self.threshold = threshold
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._load_model()

    def _load_model(self) -> nn.Module:
        if not self.model_path.exists():
            raise FileNotFoundError(f"No se encontro el modelo en: {self.model_path}")

        checkpoint = torch.load(self.model_path, map_location=self.device)

        if isinstance(checkpoint, nn.Module):
            model = checkpoint
        else:
            state_dict = checkpoint.get("state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
            model = ResNetApneaCentral()
            model.load_state_dict(state_dict)

        model.to(self.device)
        model.eval()
        return model

    def predict(self, signals: list[list[float]], normalize: bool = True) -> dict[str, Any]:
        tensor, preprocessing = prepare_signal(signals, normalize=normalize)
        tensor = tensor.to(self.device)

        with torch.no_grad():
            output = self.model(tensor)
            probability = self._to_probability(output)

        prediccion = probability >= self.threshold
        return {
            "prediccion": prediccion,
            "probabilidad": probability,
            "clase": "apnea_central" if prediccion else "sin_apnea_central",
            "threshold": self.threshold,
            "modelo": self.model_path.name,
            "preprocessing": preprocessing,
        }

    @staticmethod
    def _to_probability(output: torch.Tensor) -> float:
        output = output.detach().cpu()

        if output.ndim == 2 and output.shape[1] == 2:
            return float(torch.softmax(output, dim=1)[0, 1].item())

        return float(torch.sigmoid(output.reshape(-1)[0]).item())


_model_service: ModelService | None = None


def get_model_service() -> ModelService:
    global _model_service
    if _model_service is None:
        settings = get_settings()
        _model_service = ModelService(settings.model_path, settings.model_threshold)
    return _model_service
