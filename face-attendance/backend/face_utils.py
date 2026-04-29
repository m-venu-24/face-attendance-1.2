import base64
import io
import json
import os
from functools import lru_cache
from typing import Optional, List, Dict

import numpy as np
from PIL import Image, ImageOps

try:
    import cv2
except Exception:
    cv2 = None

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


def decode_base64_image(b64_string: str) -> np.ndarray:
    if "," in b64_string:
        b64_string = b64_string.split(",", 1)[1]
    img_bytes = base64.b64decode(b64_string)
    image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return np.array(image)


def _center_crop(image_array: np.ndarray) -> np.ndarray:
    image = Image.fromarray(image_array).convert("RGB")
    width, height = image.size
    crop_width = max(64, int(width * 0.6))
    crop_height = max(64, int(height * 0.6))
    left = max((width - crop_width) // 2, 0)
    top = max((height - crop_height) // 5, 0)
    right = min(left + crop_width, width)
    bottom = min(top + crop_height, height)
    return np.array(image.crop((left, top, right, bottom)))


def _scale_box(box, scale: float, image_width: int, image_height: int):
    x1, y1, x2, y2 = box
    center_x = (x1 + x2) / 2.0
    center_y = (y1 + y2) / 2.0
    box_width = (x2 - x1) * scale
    box_height = (y2 - y1) * scale

    left = int(max(0, center_x - box_width / 2.0))
    top = int(max(0, center_y - box_height / 2.0))
    right = int(min(image_width, center_x + box_width / 2.0))
    bottom = int(min(image_height, center_y + box_height / 2.0))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _detect_face_box_yolo(image_array: np.ndarray):
    model = _load_yolo_model()
    if model is None:
        return None

    try:
        results = model.predict(image_array, conf=0.35, verbose=False)
    except Exception:
        return None

    if not results:
        return None

    boxes = results[0].boxes
    if boxes is None or len(boxes) == 0:
        return None

    xyxy = boxes.xyxy.cpu().numpy()
    confidences = boxes.conf.cpu().numpy()
    areas = (xyxy[:, 2] - xyxy[:, 0]) * (xyxy[:, 3] - xyxy[:, 1])
    best_idx = int(np.argmax(areas * (confidences + 1e-6)))
    return tuple(xyxy[best_idx].astype(int).tolist())


def _detect_face_box_haar(image_array: np.ndarray):
    if cv2 is None:
        return None

    try:
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
        cascade = cv2.CascadeClassifier(cascade_path)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    except Exception:
        return None

    if faces is None or len(faces) == 0:
        return None

    faces = sorted(faces, key=lambda rect: rect[2] * rect[3], reverse=True)
    x, y, w, h = faces[0]
    return x, y, x + w, y + h


def _detect_face_box(image_array: np.ndarray):
    return _detect_face_box_yolo(image_array) or _detect_face_box_haar(image_array)


@lru_cache(maxsize=1)
def _load_yolo_model():
    if YOLO is None:
        return None

    model_path = os.getenv("YOLO_FACE_MODEL_PATH", "models/yolov8n-face.pt")
    if not os.path.exists(model_path):
        return None

    try:
        return YOLO(model_path)
    except Exception:
        return None


def detect_face_crop(image_array: np.ndarray) -> np.ndarray:
    face_box = _detect_face_box(image_array)
    if face_box is None:
        return _center_crop(image_array)

    x1, y1, x2, y2 = face_box
    height, width = image_array.shape[:2]
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(x1 + 1, min(x2, width))
    y2 = max(y1 + 1, min(y2, height))
    return image_array[y1:y2, x1:x2]


def _prepare_face_region(image_array: np.ndarray) -> np.ndarray:
    face_region = Image.fromarray(detect_face_crop(image_array)).convert("RGB")
    face_region = ImageOps.autocontrast(face_region)
    face_region = face_region.resize((32, 32))
    grayscale = face_region.convert("L")
    return np.asarray(grayscale, dtype=np.float32) / 255.0


def _embedding_from_crop(crop_array: np.ndarray) -> Optional[List[float]]:
    if crop_array is None or crop_array.size == 0:
        return None

    face_region = Image.fromarray(crop_array).convert("RGB")
    face_region = ImageOps.autocontrast(face_region)
    face_region = face_region.resize((32, 32))
    grayscale = np.asarray(face_region.convert("L"), dtype=np.float32) / 255.0
    if float(np.var(grayscale)) < 0.002:
        return None

    embedding = grayscale.flatten()
    embedding = (embedding - float(np.mean(embedding))) / (float(np.std(embedding)) + 1e-6)
    embedding = embedding.astype(np.float32)
    norm = float(np.linalg.norm(embedding))
    if norm == 0.0:
        return None
    return (embedding / norm).tolist()


def get_face_embedding(image_array: np.ndarray) -> Optional[List[float]]:
    embeddings = get_face_embedding_candidates(image_array)
    return embeddings[0] if embeddings else None


def get_face_embedding_candidates(image_array: np.ndarray) -> List[List[float]]:
    if image_array is None or image_array.size == 0:
        return []

    image_height, image_width = image_array.shape[:2]
    face_box = _detect_face_box(image_array)
    crops = []

    if face_box is not None:
        for scale in (0.9, 1.0, 1.15):
            scaled = _scale_box(face_box, scale, image_width, image_height)
            if scaled is None:
                continue
            left, top, right, bottom = scaled
            crops.append(image_array[top:bottom, left:right])

    crops.append(detect_face_crop(image_array))
    crops.append(_center_crop(image_array))

    embeddings = []
    seen = set()
    for crop in crops:
        embedding = _embedding_from_crop(crop)
        if embedding is None:
            continue
        fingerprint = tuple(round(value, 4) for value in embedding[:32])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        embeddings.append(embedding)
    return embeddings


def embedding_from_json(json_str: str) -> np.ndarray:
    return np.array(json.loads(json_str), dtype=np.float32)


def compare_faces(known_embeddings: List[Dict], unknown_embedding: List[float], tolerance: float = 0.5) -> Optional[Dict]:
    if not known_embeddings or not unknown_embedding:
        return None

    unknown_enc = np.array(unknown_embedding, dtype=np.float32)
    unknown_norm = float(np.linalg.norm(unknown_enc))
    if unknown_norm == 0.0:
        return None
    unknown_enc = unknown_enc / unknown_norm

    valid_embeddings = []
    for item in known_embeddings:
        known = np.array(item["embedding"], dtype=np.float32)
        norm = float(np.linalg.norm(known))
        if norm == 0.0:
            continue
        valid_embeddings.append({"student_id": item["student_id"], "embedding": known / norm})

    if not valid_embeddings:
        return None

    similarities = [float(np.dot(item["embedding"], unknown_enc)) for item in valid_embeddings]
    best_idx = int(np.argmax(similarities))
    best_similarity = similarities[best_idx]

    confidence = round(((best_similarity + 1.0) / 2.0) * 100, 2)
    return {
        "student_id": valid_embeddings[best_idx]["student_id"],
        "distance": 1.0 - best_similarity,
        "confidence": confidence,
        "matched": best_similarity >= tolerance,
    }


def count_faces_in_frame(image_array: np.ndarray) -> int:
    model = _load_yolo_model()
    if model is None:
        return 1 if get_face_embedding(image_array) is not None else 0

    try:
        results = model.predict(image_array, conf=0.35, verbose=False)
    except Exception:
        return 1 if get_face_embedding(image_array) is not None else 0

    if not results or results[0].boxes is None:
        return 0
    return int(len(results[0].boxes))
