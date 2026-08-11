import logging
import os
import re
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import UploadFile
from pyedflib import EdfReader

from app.ml.preprocessing import EXPECTED_CHANNELS

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".edf", ".dat", ".apn"}


def parse_signal_file(file: UploadFile) -> tuple[list[list[float]], dict[str, Any]]:
    filename = Path(file.filename or "")
    extension = filename.suffix.lower()

    logger.info(f"Iniciando parseo de archivo de señal: '{file.filename}' (extensión: '{extension}')")

    if extension not in SUPPORTED_EXTENSIONS:
        logger.warning(f"Formato no soportado '{extension}' para archivo '{file.filename}'")
        raise ValueError("Archivo no soportado. Use .edf, .dat o .apn.")

    file.file.seek(0)
    if extension == ".edf":
        signals = _read_edf(file)
    else:
        signals = _read_text_signal(file)

    metadata = {
        "file_name": file.filename,
        "file_format": extension.lstrip('.'),
        "sample_count": len(signals),
        "channel_count": len(signals[0]) if signals else 0,
    }
    logger.info(
        f"Parseo exitoso de '{file.filename}': "
        f"{metadata['sample_count']} muestras, {metadata['channel_count']} canales."
    )
    return signals, metadata


def _read_edf(file: UploadFile) -> list[list[float]]:
    file.file.seek(0)
    content = file.file.read()
    logger.debug(f"Guardando archivo EDF temporal para '{file.filename}' ({len(content)} bytes)")

    with tempfile.NamedTemporaryFile(suffix=".edf", delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        with EdfReader(temp_path) as edf:
            n_channels = edf.signals_in_file
            logger.debug(f"Lectura EDF: detectados {n_channels} canales de señal")
            signals = [edf.readSignal(idx).astype(np.float32) for idx in range(n_channels)]
            if not signals:
                raise ValueError("El archivo EDF no contiene señales válidas.")
            stacked = np.stack(signals, axis=1)
            return stacked.tolist()
    except Exception as exc:
        logger.error(f"Error procesando estructura EDF de '{file.filename}': {exc}")
        raise ValueError(f"Error leyendo el archivo EDF: {exc}") from exc
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _read_text_signal(file: UploadFile) -> list[list[float]]:
    file.file.seek(0)
    raw = file.file.read()
    if isinstance(raw, bytes):
        raw_text = raw.decode("utf-8", errors="replace")
    else:
        raw_text = str(raw)

    rows: list[list[float]] = []
    for line in StringIO(raw_text):
        stripped = line.strip()
        if not stripped:
            continue

        parts = re.split(r"[\s,;]+", stripped)
        values = []
        for part in parts:
            try:
                values.append(float(part))
            except ValueError:
                continue

        if values:
            rows.append(values)

    if not rows:
        logger.warning(f"No se encontraron datos numéricos en el archivo '{file.filename}'")
        raise ValueError("No se encontraron datos numéricos en el archivo.")

    data = np.asarray(rows, dtype=np.float32)
    if data.ndim == 1:
        if data.size % EXPECTED_CHANNELS == 0:
            data = data.reshape(-1, EXPECTED_CHANNELS)
        else:
            data = data.reshape(-1, 1)

    if data.ndim != 2:
        logger.warning(f"Forma inválida de matriz de datos ({data.ndim}D) en '{file.filename}'")
        raise ValueError("El contenido del archivo no tiene una forma válida de señales.")

    logger.debug(f"Matriz de señal de texto construida con forma: {data.shape}")
    return data.tolist()

