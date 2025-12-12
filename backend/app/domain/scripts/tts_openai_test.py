"""
OpenAI TTS (Text-to-Speech) 테스트

OpenAI의 TTS API를 사용하여 한국어 음성 파일을 생성합니다.
- 모델: tts-1 (빠름) 또는 tts-1-hd (고품질)
- 음성: alloy, echo, fable, onyx, nova, shimmer
"""

from openai import OpenAI
from pathlib import Path
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def test_openai_tts():
    """OpenAI TTS 테스트"""
    
    # OpenAI 클라이언트 초기화
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # 생성할 텍스트 (애니메이션 캐릭터 느낌)
    text = """
    안녕하세요! 저는 Virtual Assistant예요!
    오늘도 힘내세요! 제가 도와드릴게요!
    """
    
    # 출력 파일 경로
    output_dir = Path(__file__).parent
    output_file = output_dir / "openai_tts_shimmer.mp3"
    
    print("🎤 OpenAI TTS 음성 생성 중...")
    print(f"📝 텍스트: {text.strip()}")
    print(f"🔊 음성: shimmer (여성, 가장 밝고 부드러운)")
    print(f"🎵 모델: tts-1-hd (고품질)")
    
    try:
        # TTS 생성
        response = client.audio.speech.create(
            model="tts-1-hd",  # tts-1 (빠름) 또는 tts-1-hd (고품질)
            voice="shimmer",   # shimmer가 가장 젊고 밝은 목소리
            input=text.strip()
        )
        
        # 파일 저장
        response.stream_to_file(str(output_file))
        
        print(f"✅ 완료: {output_file} 생성됨")
        print(f"📊 파일 크기: {output_file.stat().st_size / 1024:.2f} KB")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")


def test_all_voices():
    """6가지 음성으로 모두 테스트"""
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    output_dir = Path(__file__).parent
    
    voices = {
        "alloy": "중성적, 균형잡힌 음성",
        "echo": "남성적, 차분한 음성",
        "fable": "영국식, 따뜻한 음성",
        "onyx": "남성적, 깊은 음성",
        "nova": "여성적, 밝은 음성",
        "shimmer": "여성적, 부드러운 음성"
    }
    
    text = "안녕하세요. 저는 Virtual Assistant입니다."
    
    print("🎤 6가지 음성으로 테스트 중...\n")
    
    for voice, description in voices.items():
        output_file = output_dir / f"openai_tts_{voice}.mp3"
        
        try:
            print(f"🔊 {voice} ({description}) 생성 중...")
            
            response = client.audio.speech.create(
                model="tts-1",  # 빠른 버전
                voice=voice,
                input=text
            )
            
            response.stream_to_file(str(output_file))
            
            size_kb = output_file.stat().st_size / 1024
            print(f"   ✅ {output_file.name} ({size_kb:.2f} KB)\n")
            
        except Exception as e:
            print(f"   ❌ 오류: {e}\n")


if __name__ == "__main__":
    # 기본 테스트 (nova 음성)
    test_openai_tts()
    
    # 모든 음성 테스트를 원하면 주석 해제
    # print("\n" + "="*60 + "\n")
    # test_all_voices()

