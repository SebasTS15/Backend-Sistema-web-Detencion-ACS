import logging
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)

EXPECTED_SAMPLES = 3840
EXPECTED_CHANNELS = 3
EXPECTED_CHANNEL_NAMES = ["FLOW_IDX", "THO_IDX", "ABD_IDX"]


def prepare_signal(
    signals: list[list[float]],
    normalize: bool = True,
    channel_names: list[str] | None = None,
) -> tuple[torch.Tensor, dict[str, Any]]:
    """
    Prepara señales para el modelo, validando que sean compatibles con los canales de entrenamiento.
    """
    array = np.asarray(signals, dtype=np.float32)

    if array.ndim != 2:
        logger.warning(f"Error de dimensiones en signals: {array.ndim}D en lugar de 2D.")
        raise ValueError("signals debe ser una matriz 2D con forma [muestras, canales].")

    original_shape = list(array.shape)
    logger.info(f"Iniciando preprocesamiento de señal. Forma original [muestras, canales]: {original_shape}")

    # Validar nombres de canales si se proporcionan
    if channel_names is not None:
        _validate_channel_names(channel_names)

    array = _fit_channels(array, EXPECTED_CHANNELS)
    array = _fit_samples(array, EXPECTED_SAMPLES)

    if normalize:
        logger.debug("Aplicando normalización z-score por canal...")
        array = _normalize_per_channel(array)

    tensor = torch.from_numpy(array.T).unsqueeze(0).float()
    info = {
        "original_shape": original_shape,
        "processed_shape": [EXPECTED_SAMPLES, EXPECTED_CHANNELS],
        "normalized": normalize,
        "channel_names": channel_names or EXPECTED_CHANNEL_NAMES,
    }
    logger.info(
        f"Preprocesamiento finalizado con éxito. Forma final de tensor para PyTorch: {tuple(tensor.shape)}"
    )
    return tensor, info


def _fit_channels(array: np.ndarray, expected_channels: int) -> np.ndarray:
    current_channels = array.shape[1]
    if current_channels == expected_channels:
        return array
    if current_channels > expected_channels:
        logger.info(f"Ajuste de canales: recortando de {current_channels} a {expected_channels} canales.")
        return array[:, :expected_channels]

    logger.info(f"Ajuste de canales: agregando padding de {current_channels} a {expected_channels} canales.")
    padding = np.zeros((array.shape[0], expected_channels - current_channels), dtype=np.float32)
    return np.concatenate([array, padding], axis=1)


def _fit_samples(array: np.ndarray, expected_samples: int) -> np.ndarray:
    current_samples = array.shape[0]
    if current_samples == expected_samples:
        return array
    if current_samples > expected_samples:
        logger.info(f"Ajuste de muestras: recortando de {current_samples} a {expected_samples} muestras.")
        return array[:expected_samples, :]

    logger.info(f"Ajuste de muestras: agregando padding de {current_samples} a {expected_samples} muestras.")
    padding = np.zeros((expected_samples - current_samples, array.shape[1]), dtype=np.float32)
    return np.concatenate([array, padding], axis=0)


def _normalize_per_channel(array: np.ndarray) -> np.ndarray:
    mean = array.mean(axis=0, keepdims=True)
    std = array.std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    return (array - mean) / std


def _validate_channel_names(channel_names: list[str]) -> None:
    if len(channel_names) != EXPECTED_CHANNELS:
        logger.warning(
            f"Cantidad de canales inválida ({len(channel_names)}). Se esperaban {EXPECTED_CHANNELS}."
        )
        raise ValueError(
            f"Se esperan {EXPECTED_CHANNELS} canales, pero se recibieron {len(channel_names)}."
        )

    invalid_channels = [ch for ch in channel_names if ch not in EXPECTED_CHANNEL_NAMES]
    if invalid_channels:
        logger.warning(f"Canales no reconocidos: {invalid_channels}")
        raise ValueError(
            f"Canales no válidos: {invalid_channels}. "
            f"Se esperan: {EXPECTED_CHANNEL_NAMES}"
        )

    missing_channels = [ch for ch in EXPECTED_CHANNEL_NAMES if ch not in channel_names]
    if missing_channels:
        logger.warning(f"Canales faltantes: {missing_channels}")
        raise ValueError(
            f"Faltan canales requeridos: {missing_channels}. "
            f"Se esperan: {EXPECTED_CHANNEL_NAMES}"
        )

