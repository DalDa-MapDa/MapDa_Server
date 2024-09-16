import cv2
import pytesseract
import re
import numpy as np
from fastapi import APIRouter, File, UploadFile
from typing import List
from PIL import Image
import io
import os

router = APIRouter()

# Tesseract 실행 파일 경로 설정 (설치된 Tesseract 경로로 변경)
pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'  # MacOS에 맞춘 경로

# Tesseract 언어 파일 경로 (로컬 경로 지정)
TESSDATA_DIR = os.path.join(os.path.dirname(__file__), 'tessdata')

# 이미지 전처리 함수
def preprocess_image(image_bytes):
    # 이미지를 메모리에서 불러오기
    image = Image.open(io.BytesIO(image_bytes))
    
    # 이미지를 OpenCV 형식으로 변환 (Pillow -> OpenCV)
    image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # 이미지 확대 (텍스트 인식률을 높이기 위해 확대)
    image = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # 그레이스케일로 변환
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Adaptive Thresholding 적용 (더 나은 이진화)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
    )

    print('전처리된 데이터:', thresh)
    
    return thresh


# 텍스트에서 시간표를 파싱하는 함수
def parse_timetable(text: str) -> List[dict]:
    timetable = []
    lines = text.split('\n')
    
    day_pattern = r'(월|화|수|목|금|토|일)'
    time_pattern = r'\d{1,2}[:]\d{2}\s*-\s*\d{1,2}[:]\d{2}'
    room_pattern = r'S\d{3,4}'
    
    current_day = None
    current_time = None
    current_room = None

    for line in lines:
        if re.search(day_pattern, line):
            current_day = line.strip()
        elif re.search(time_pattern, line):
            current_time = line.strip()
        elif re.search(room_pattern, line):
            current_room = line.strip()
        else:
            if current_day and current_time and current_room:
                timetable.append({
                    "day": current_day,
                    "time": current_time,
                    "room": current_room,
                    "class": line.strip()  # 수업명
                })
                current_day = current_time = current_room = None
    
    return timetable

# 텍스트 추출 및 JSON 반환 라우터
@router.post("/timetable_upload")
async def timetable_upload(file: UploadFile = File(...)):
    content = await file.read()

    # 이미지 전처리
    processed_image = preprocess_image(content)
    print('처리된 데이터:',processed_image)

    # Tesseract에서 사용하는 언어 경로를 지정 (로컬 tessdata 디렉토리 사용)
    custom_config = f'--tessdata-dir {TESSDATA_DIR}'
    print('커스텀 컨피그:',custom_config)
    
    # 이미지에서 텍스트 추출
    extracted_text = pytesseract.image_to_string(processed_image, lang='kor+eng', config=custom_config)
    print('추출된 데이터:',extracted_text)
    
    # 텍스트에서 시간표 파싱
    timetable = parse_timetable(extracted_text)
    print('파싱된 데이터:',timetable)
    return {"timetable": timetable}
