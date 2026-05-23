"""
AetherPDF PyInstaller 빌드 자동화 스크립트.

이 스크립트는 PySide6 및 PyMuPDF(fitz) 라이브러리를 포함하여
윈도우 환경에서 단독 실행 가능한 AetherPDF.exe 파일을 빌드합니다.
빌드 전 assets/icon.png를 assets/icon.ico로 자동 변환하여
실행 파일 자체 아이콘에도 반영합니다.
"""

import os
import sys
import subprocess


def convert_png_to_ico(png_path: str, ico_path: str) -> bool:
    """
    PySide6의 QImage를 활용하여 PNG 이미지를 ICO 형식으로 변환합니다.

    Args:
        png_path (str): 원본 PNG 파일 절대 경로.
        ico_path (str): 생성할 ICO 파일 절대 경로.

    Returns:
        bool: 변환 성공 여부.
    """
    try:
        from PySide6.QtGui import QImage
        from PySide6.QtCore import QSize
        from PySide6.QtWidgets import QApplication

        # QImage를 사용하기 위해 최소한의 QApplication 인스턴스가 필요할 수 있음
        # (headless 환경에서도 안전하게 동작)
        _app = QApplication.instance()
        if _app is None:
            _app = QApplication([])

        img = QImage(png_path)
        if img.isNull():
            print(f"[Warning] PNG 이미지 로드 실패: {png_path}")
            return False

        # ICO에 필요한 다중 해상도 이미지를 256x256으로 스케일링
        from PySide6.QtCore import Qt as QtConst
        scaled = img.scaled(
            QSize(256, 256),
            QtConst.KeepAspectRatio,
            QtConst.SmoothTransformation
        )
        success = scaled.save(ico_path, "ICO")
        if success:
            print(f"[AetherPDF] PNG → ICO 변환 성공: {ico_path}")
        else:
            # ICO 직접 저장이 안 되는 경우 BMP로 우회 저장 후 .ico 확장자로 복사
            # (Qt ICO 쓰기 플러그인 미지원 시 BMP 포맷으로 대체)
            bmp_path = ico_path.replace(".ico", ".bmp")
            scaled.save(bmp_path, "BMP")
            import shutil
            shutil.copy2(bmp_path, ico_path)
            os.remove(bmp_path)
            print(f"[AetherPDF] PNG → ICO 우회 변환(BMP 경유) 완료: {ico_path}")
            success = True

        return success
    except Exception as e:
        print(f"[Warning] 아이콘 변환 중 예외 발생: {str(e)}")
        return False


def build_executable() -> None:
    """
    PyInstaller를 사용하여 AetherPDF 독립형 단일 실행 파일(.exe)을 빌드합니다.

    --onefile: 단일 실행 파일 생성
    --noconsole: 실행 시 콘솔 창 숨김
    --clean: 빌드 전 캐시 삭제
    --icon: 고양이 발바닥 아이콘을 exe 자체 리소스에 삽입
    --add-data: assets 디렉토리를 번들에 포함하여 런타임 시 아이콘 접근 보장
    """
    print("[AetherPDF] 독립형 .exe 빌드 파이프라인 시작...")

    # 가상환경의 pyinstaller 경로 획득
    pyinstaller_bin = os.path.join(".venv", "Scripts", "pyinstaller.exe")
    if not os.path.exists(pyinstaller_bin):
        pyinstaller_bin = os.path.abspath(pyinstaller_bin)
        if not os.path.exists(pyinstaller_bin):
            print("[Error] 가상환경 내 pyinstaller.exe를 찾을 수 없습니다. 설치를 확인하세요.")
            sys.exit(1)

    entry_point = "main.py"
    if not os.path.exists(entry_point):
        print(f"[Error] 진입점 파일인 {entry_point}가 존재하지 않습니다.")
        sys.exit(1)

    # [NEW] 아이콘 자동 변환: assets/icon.png → assets/icon.ico
    icon_png = os.path.join("assets", "icon.png")
    icon_ico = os.path.join("assets", "icon.ico")
    icon_arg = None

    if os.path.exists(icon_png):
        print(f"[AetherPDF] 아이콘 PNG 감지됨: {icon_png}")
        if convert_png_to_ico(icon_png, icon_ico):
            icon_arg = f"--icon={icon_ico}"
        else:
            print("[Warning] ICO 변환에 실패하여 기본 아이콘으로 빌드합니다.")
    else:
        print(f"[Warning] 아이콘 파일 없음: {icon_png}. 기본 아이콘으로 빌드합니다.")

    # PyInstaller 빌드 아규먼트 리스트
    args = [
        pyinstaller_bin,
        "--clean",
        "--onefile",
        "--noconsole",
        "--name=AetherPDF",
        # assets 디렉토리를 번들에 포함하여 런타임 시 아이콘 및 리소스 접근 보장
        f"--add-data=assets{os.pathsep}assets",
    ]

    # 변환된 ICO 파일이 존재하면 exe 자체 아이콘으로 삽입
    if icon_arg:
        args.append(icon_arg)

    args.append(entry_point)

    print(f"[AetherPDF] 실행할 PyInstaller 명령어: {' '.join(args)}")

    try:
        # 빌드 프로세스 구동
        result = subprocess.run(args, check=True)
        if result.returncode == 0:
            print("\n[AetherPDF] 독립형 빌드가 성공적으로 완료되었습니다!")
            print("[AetherPDF] 출력 파일 경로: dist/AetherPDF.exe")
        else:
            print(f"\n[Error] 빌드 중 오류가 발생했습니다. (Exit Code: {result.returncode})")
    except subprocess.CalledProcessError as e:
        print(f"\n[Error] PyInstaller 프로세스 실행 중 예외 발생: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()
