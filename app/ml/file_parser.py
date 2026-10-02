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


SUPPORTED_EXTENSIONS = {".edf", ".dat", ".apn"}


def parse_signal_file(file: UploadFile) -> tuple[np.ndarray, dict[str, Any]]:
    filename = Path(file.filename or "")
    extension = filename.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Archivo no soportado. Use .edf, .dat o .apn.")

    file.file.seek(0)
    if extension == ".edf":
        signals = _read_edf(file)
    else:
        signals = _read_text_signal(file)

    metadata = {
        "file_name": file.filename,
        "file_format": extension.lstrip('.'),
        "sample_count": int(signals.shape[0]),
        "channel_count": int(signals.shape[1]) if signals.ndim > 1 else 1,
    }
    return signals, metadata


def _sanitize_edf_header(content: bytes) -> bytes:
    """
    Sanitiza los encabezados principal y de canales EDF (bytes 0..header_bytes) corrigiendo:
    - Bytes no-ASCII (<32 o >127) en Patient ID, Recording ID, etiquetas, transductores y prefiltros.
    - Separadores no conformes (':', '/', '-', espacio) en fecha y hora de inicio (bytes 168..184).
    """
    if len(content) < 256:
        return content
    b = bytearray(content)

    # Obtener el tamaño total del encabezado (bytes 184..192)
    try:
        header_size_str = bytes(b[184:192]).decode("ascii", errors="ignore").strip()
        header_bytes = int(header_size_str)
    except ValueError:
        header_bytes = 256

    header_limit = min(len(b), max(256, header_bytes))

    # Reemplazar bytes no-ASCII o de control no imprimibles en todos los bloques de encabezado
    for i in range(header_limit):
        if b[i] > 127 or b[i] < 32:
            b[i] = ord(" ")

    # Startdate (bytes 168..176) y Starttime (bytes 176..184)
    for i in range(168, 184):
        if b[i] in (ord(":"), ord("/"), ord("-"), ord(" ")):
            b[i] = ord(".")
        elif b[i] > 127:
            b[i] = ord("0")

    return bytes(b)


def _read_edf(file: UploadFile) -> np.ndarray:
    file.file.seek(0)
    content = file.file.read()
    content = _sanitize_edf_header(content)

    with tempfile.NamedTemporaryFile(suffix=".edf", delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        with EdfReader(temp_path) as edf:
            n_channels = edf.signals_in_file
            raw_signals: list[tuple[str, np.ndarray]] = []

            for idx in range(n_channels):
                try:
                    header = edf.getSignalHeader(idx)
                    label = header.get("label", "").strip()
                    # Ignorar canales de anotaciones EDF+
                    if "annotation" in label.lower():
                        continue

                    sig = edf.readSignal(idx).astype(np.float32)
                    if sig.size > 0:
                        raw_signals.append((label, sig))
                except Exception:
                    continue

            if not raw_signals:
                raise ValueError("El archivo EDF no contiene señales numéricas válidas.")

            return _align_and_select_channels(raw_signals)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"Error leyendo el archivo EDF: {exc}") from exc
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def _align_and_select_channels(raw_signals: list[tuple[str, np.ndarray]]) -> np.ndarray:
    """
    Selecciona los canales más relevantes y los alinea si tienen diferentes frecuencias de muestreo.
    """
    flow_sig, tho_sig, abd_sig = None, None, None

    for label, sig in raw_signals:
        lbl = label.lower()
        if flow_sig is None and any(k in lbl for k in ["flow", "flw", "nasal", "air", "resp_flow"]):
            flow_sig = sig
        elif tho_sig is None and any(k in lbl for k in ["tho", "thor", "chest", "rib", "thoracic"]):
            tho_sig = sig
        elif abd_sig is None and any(k in lbl for k in ["abd", "abdo", "abdomen", "abdominal"]):
            abd_sig = sig

    matched = [s for s in [flow_sig, tho_sig, abd_sig] if s is not None]

    if len(matched) < EXPECTED_CHANNELS:
        selected_sigs = [sig for _, sig in raw_signals]
    else:
        selected_sigs = matched

    max_len = max(len(s) for s in selected_sigs)
    aligned_signals: list[np.ndarray] = []

    for s in selected_sigs:
        if len(s) == max_len:
            aligned_signals.append(s)
        else:
            x_old = np.linspace(0, 1, len(s))
            x_new = np.linspace(0, 1, max_len)
            resampled = np.interp(x_new, x_old, s).astype(np.float32)
            aligned_signals.append(resampled)

    return np.stack(aligned_signals, axis=1)


def _read_text_signal(file: UploadFile) -> np.ndarray:
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
        raise ValueError("No se encontraron datos numéricos en el archivo.")

    data = np.asarray(rows, dtype=np.float32)
    if data.ndim == 1:
        if data.size % EXPECTED_CHANNELS == 0:
            data = data.reshape(-1, EXPECTED_CHANNELS)
        else:
            data = data.reshape(-1, 1)

    if data.ndim != 2:
        raise ValueError("El contenido del archivo no tiene una forma válida de señales.")

    return data
