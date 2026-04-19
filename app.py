import streamlit as st
import yt_dlp
import google.generativeai as genai
import os
import tempfile
import time

# --- Setup & Config ---
st.set_page_config(page_title="인스타 릴스 대본 추출기 (Gemini)", page_icon="🧩", layout="centered")

# --- CSS Styling ---
st.markdown("""
<style>
.main {
    background-color: #f8f9fa;
}
.stTextInput>div>div>input {
    border-radius: 10px;
    border: 2px solid #ddd;
    box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.05);
}
.stButton>button {
    width: 100%;
    border-radius: 10px;
    background: linear-gradient(90deg, #E1306C, #FD1D1D, #F56040, #FFDC80);
    color: white;
    font-weight: bold;
    border: none;
    transition: 0.3s;
}
.stButton>button:hover {
    transform: scale(1.02);
    box-shadow: 0px 5px 15px rgba(225, 48, 108, 0.4);
}
</style>
""", unsafe_allow_html=True)

# --- Core Functions ---

def download_audio_with_progress(url, output_path, progress_bar, status_text, cookies_path=None):
    def my_hook(d):
        if d['status'] == 'downloading':
            try:
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded_bytes = d.get('downloaded_bytes', 0)
                if total_bytes:
                    percent = min(downloaded_bytes / total_bytes, 1.0)
                    progress_bar.progress(percent)
                    status_text.write(f"📥 다운로드 중... {percent*100:.1f}%")
            except Exception:
                pass
        elif d['status'] == 'finished':
            progress_bar.progress(1.0)
            status_text.write("📥 다운로드 완료! 오디오 준비 중...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'progress_hooks': [my_hook],
    }
    
    # 쿠키 파일이 제공된 경우 옵션에 추가
    if cookies_path and os.path.exists(cookies_path):
        ydl_opts['cookiefile'] = cookies_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# --- UI Layout ---

st.title("🧩 릴스 대본 추출기 (Gemini AI)")
st.markdown("**인스타그램 릴스(Reel) 주소**를 넣으면 구글 제미나이(Google Gemini) AI가 영상의 말소리를 분석해 대본으로 구워줍니다!")

st.markdown("---")

gemini_api_key = st.text_input("🔑 본인의 Gemini API Key를 입력하세요:", type="password", placeholder="AI Studio에서 발급받은 API Key (AIzaSy...)")
url = st.text_input("🔗 여기에 인스타그램 릴스 주소를 붙여넣으세요:", placeholder="https://www.instagram.com/reel/...")

with st.expander("⚠️ 인스타그램 접속 에러(다운로드 실패)가 나나요? 클릭해서 해결법 보기"):
    st.markdown("""
    인스타그램이 자체적으로 로봇(자동 다운로드) 접속을 막아서 발생하는 에러입니다.
    이 브라우저에 쿠키 파일(`cookies.txt`)을 업로드하면 사람처럼 인증되어 정상 다운로드가 가능합니다.
    1. 크롬 확장프로그램 [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) 설치
    2. 인스타그램 웹사이트 로그인 상태에서 위 확장프로그램 아이콘 클릭 후 `Export` 눌러 다운로드
    3. 다운받은 `cookies.txt` 파일을 아래에 업로드하세요. (개인정보는 서버에 저장되지 않고 즉시 폐기됩니다!)
    """)
    cookies_upload = st.file_uploader("🍪 (선택) Instagram 쿠키 파일 업로드", type=["txt"])

if st.button("🚀 대본 추출 시작"):
    if not gemini_api_key:
        st.warning("먼저 Gemini API Key를 입력해주세요!")
    elif not url:
        st.warning("먼저 릴스 주소를 입력해주세요!")
    elif "instagram.com" not in url:
        st.warning("앗! 인스타그램 릴스 주소(`instagram.com/...`)가 아닌 것 같아요. 올바른 릴스 영상 링크를 붙여넣었는지 확인해주세요!")
    else:
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        
        with st.status("작업을 진행 중입니다...", expanded=True) as status:
            with tempfile.TemporaryDirectory() as tmpdirname:
                audio_path = os.path.join(tmpdirname, "audio_file")
                mp3_path = audio_path + ".mp3"
                
                # 임시 쿠키 파일 생성
                cookies_path = None
                if cookies_upload is not None:
                    cookies_path = os.path.join(tmpdirname, "cookies.txt")
                    with open(cookies_path, "wb") as f:
                        f.write(cookies_upload.getvalue())
                
                # 1. Download Audio
                st.write("### 1. 인스타그램 오디오 다운로드")
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                status_text.write("📥 데이터 연결 준비 중...")
                
                try:
                    download_audio_with_progress(url, audio_path, progress_bar, status_text, cookies_path)
                except Exception as e:
                    status.update(label="다운로드 실패!", state="error", expanded=True)
                    st.error(f"영상을 가져올 수 없습니다. 비공개 영상이거나 주소가 올바른지 확인해주세요. (에러: {e})")
                    st.stop()
                
                # 2. Transcribe Audio (Gemini API)
                st.write("---")
                st.write("### 2. Gemini 2.5 Flash 모델 분석 진행")
                st.info("🧠 최신 제미나이가 오디오를 듣고 텍스트로 타이핑하고 있습니다. (잠시만 기다려주세요!)")
                
                try:
                    start_time = time.time()
                    
                    # Upload to Gemini
                    st.write("🔼 오디오 파일을 클라우드에 업로드 중...")
                    uploaded_file = genai.upload_file(mp3_path)
                    
                    # Generate Transcript
                    st.write("📝 대본 작성 중...")
                    model = genai.GenerativeModel('models/gemini-2.5-flash')
                    prompt = "이 오디오에서 사람들이 하는 말을 그대로 적어줘. 다른 부연 설명이나 인사말 없이 오직 들리는 내용만 대본 형태의 텍스트로 출력해줘."
                    
                    response = model.generate_content([prompt, uploaded_file])
                    extracted_text = response.text
                    
                    # Cleanup
                    st.write("🧹 임시 파일 정리 중...")
                    genai.delete_file(uploaded_file.name)
                    
                    end_time = time.time()
                except Exception as e:
                    status.update(label="음성 분석 실패!", state="error", expanded=True)
                    st.error(f"음성을 분석하는 도중 오류가 발생했습니다. API 키가 유효한지 확인해보세요. (에러: {e})")
                    st.stop()
                
                # 3. Done
                status.update(label="모든 작업 처리가 완료되었습니다! 🎉", state="complete", expanded=False)
                
        # --- Display Results ---
        st.success(f"대본 추출 성공! (처리 시간: {end_time - start_time:.1f}초)")
        
        st.markdown("### 📝 추출된 대본:")
        
        # Display the text in a large text area so it's easy to copy
        st.text_area(label="대본 원본", value=extracted_text, height=300, label_visibility="collapsed")
        
        # Allow user to download as a text file
        st.download_button(
            label="💾 .txt 파일로 저장(다운로드)",
            data=extracted_text,
            file_name="reels_gemini_script.txt",
            mime="text/plain",
            use_container_width=True
        )
