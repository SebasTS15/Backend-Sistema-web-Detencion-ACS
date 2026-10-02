
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
    Sanitiza el encabezado EDF principal y de canales corrigiendo:
    - Caracteres no-ASCII (<32 o >127) en Patient ID, Recording ID, etiquetas, transductores y prefiltros.
    - Separadores no conformes (':', '/', '-') en fecha y hora de inicio (bytes 168..184).
    - Normalización de límites físicos y digitales si los campos presentan inconsistencias.
    """
    if len(content) < 256:
        return content
    b = bytearray(content)

    # Reemplazar caracteres no-ASCII en Patient ID (bytes 8..88) y Recording ID (bytes 88..168)
    for i in range(8, 168):
        if b[i] > 127:
            b[i] = ord(" ")

    # Startdate (bytes 168..176) y Starttime (bytes 176..184): corregir separadores no conformes
    for i in range(168, 184):
        if b[i] in (ord(":"), ord("/"), ord("-")):
            b[i] = ord(".")

    # Normalizar campos de min/max físico y digital de los canales para evitar errores de pyedflib
    try:
        n_channels = int(bytes(b[252:256]).decode("ascii", errors="ignore").strip())
        offset_pmin = 256 + n_channels * 16 + n_channels * 80 + n_channels * 8
        offset_pmax = offset_pmin + n_channels * 8
        offset_dmin = offset_pmax + n_channels * 8
        offset_dmax = offset_dmin + n_channels * 8

        for i in range(n_channels):
            try:
                pmin_val = float(bytes(b[offset_pmin + i * 8 : offset_pmin + (i + 1) * 8]).decode("ascii", errors="ignore").strip())
                pmax_val = float(bytes(b[offset_pmax + i * 8 : offset_pmax + (i + 1) * 8]).decode("ascii", errors="ignore").strip())
                dmin_val = int(bytes(b[offset_dmin + i * 8 : offset_dmin + (i + 1) * 8]).decode("ascii", errors="ignore").strip())
                dmax_val = int(bytes(b[offset_dmax + i * 8 : offset_dmax + (i + 1) * 8]).decode("ascii", errors="ignore").strip())
                if pmin_val >= pmax_val:
                    pmin_val, pmax_val = -800.0, 800.0
                if dmin_val >= dmax_val:
                    dmin_val, dmax_val = -2000, 2000
            except Exception:
                pmin_val, pmax_val = -800.0, 800.0
                dmin_val, dmax_val = -2000, 2000

            b[offset_pmin + i * 8 : offset_pmin + (i + 1) * 8] = str(pmin_val).ljust(8)[:8].encode("ascii")
            b[offset_pmax + i * 8 : offset_pmax + (i + 1) * 8] = str(pmax_val).ljust(8)[:8].encode("ascii")
            b[offset_dmin + i * 8 : offset_dmin + (i + 1) * 8] = str(dmin_val).ljust(8)[:8].encode("ascii")
            b[offset_dmax + i * 8 : offset_dmax + (i + 1) * 8] = str(dmax_val).ljust(8)[:8].encode("ascii")
    except Exception:
        pass

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
            headers: list[tuple[int, str]] = []

            for idx in range(n_channels):
                try:
                    lbl = edf.getSignalHeader(idx).get("label", "").strip()
                    if "annotation" not in lbl.lower():
                        headers.append((idx, lbl))
                except Exception:
                    continue

            if not headers:
                raise ValueError("El archivo EDF no contiene señales numéricas válidas.")

            # Seleccionar previamente los canales necesarios antes de cargar la señal a RAM
            selected_channels = _select_target_channel_indices(headers)

            raw_signals: list[tuple[str, np.ndarray]] = []
            for idx, label in selected_channels:
                try:
                    sig = edf.readSignal(idx).astype(np.float32)
                    if sig.size > 0:
                        raw_signals.append((label, sig))
                except Exception:
                    continue

            if not raw_signals:
                raise ValueError("No se pudieron leer las señales del archivo EDF.")

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


def _select_target_channel_indices(headers: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """
    Identifica hasta EXPECTED_CHANNELS (3) canales relevantes (Flujo, Tórax, Abdomen) antes de leer datos.
    """
    flow, tho, abd = None, None, None

    for idx, label in headers:
        lbl = label.lower()
        if flow is None and any(k in lbl for k in ["flow", "flw", "nasal", "air", "naf", "resp_flow"]):
            flow = (idx, label)
        elif tho is None and any(k in lbl for k in ["tho", "thor", "chest", "rib", "vth", "thoracic"]):
            tho = (idx, label)
        elif abd is None and any(k in lbl for k in ["abd", "abdo", "abdomen", "vab", "abdominal"]):
            abd = (idx, label)

    selected = [ch for ch in [flow, tho, abd] if ch is not None]

    if len(selected) < EXPECTED_CHANNELS:
        used_indices = {idx for idx, _ in selected}
        for ch in headers:
            if ch[0] not in used_indices:
                selected.append(ch)
                if len(selected) == EXPECTED_CHANNELS:
                    break

    return selected


def _align_and_select_channels(raw_signals: list[tuple[str, np.ndarray]]) -> np.ndarray:
    """
    Alinea los canales seleccionados si tienen diferentes frecuencias de muestreo.
    """
    selected_sigs = [sig for _, sig in raw_signals]
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
