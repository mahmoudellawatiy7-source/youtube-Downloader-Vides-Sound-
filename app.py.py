import streamlit as st
import subprocess
import re
import os
import json
import shutil
import sys

# إعدادات الصفحة العامة للتطبيق
st.set_page_config(
    page_title="منصة تحميل ومعالجة الوسائط",
    page_icon="📥",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# الواجهة الرسومية والهوية المهنية
st.title("📥 منصة تحميل وتقصيص مقاطع الفيديو")
st.markdown("### **إعداد وتطوير: البروف دكتور محمود اللواتي**")
st.markdown("---")

# التأكد من وجود المجلدات المؤقتة
WORKDIR = 'yt_web_work'
if not os.path.exists(WORKDIR):
    os.makedirs(WORKDIR, exist_ok=True)

QUALITY_ORDER = ['1440', '1080', '720', '480', '360']
AUDIO_CODEC_MAP = {
    'mp3':  ['-vn', '-acodec', 'libmp3lame', '-q:a', '2'],
    'wav':  ['-vn', '-acodec', 'pcm_s16le'],
    'aac':  ['-vn', '-acodec', 'aac', '-b:a', '192k'],
    'flac': ['-vn', '-acodec', 'flac'],
    'ogg':  ['-vn', '-acodec', 'libvorbis', '-q:a', '4'],
    'm4a':  ['-vn', '-acodec', 'aac', '-b:a', '192k'],
}

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name).strip()

def parse_time(raw):
    raw = str(raw).strip()
    if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', raw):
        p = raw.split(':')
        return f'{int(p[0]):02d}:{int(p[1]):02d}:00' if len(p) == 2 else f'{int(p[0]):02d}:{int(p[1]):02d}:{int(p[2]):02d}'
    return "00:00:00"

def to_sec(t):
    h, m, s = map(int, t.split(':'))
    return h * 3600 + m * 60 + s

def run_quiet(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def quality_format_chain(requested_quality):
    if requested_quality == "أعلى جودة متاحة" or not requested_quality:
        return 'bestvideo+bestaudio/best'
    start_idx = QUALITY_ORDER.index(requested_quality)
    chain_parts = [f'bestvideo[height<={q}]+bestaudio' for q in QUALITY_ORDER[start_idx:]]
    chain_parts.append('bestvideo+bestaudio')
    chain_parts.append('best')
    return '/'.join(chain_parts)

# --- نموذج المدخلات الرقمية ---
video_url = st.text_input("🔗 أدخل رابط الفيديو أو قائمة التشغيل (YouTube URL):")

col1, col2 = st.columns(2)
with col1:
    quality_selection = st.selectbox("📺 الجودة المطلوبة:", ["1080", "1440", "720", "480", "360", "أعلى جودة متاحة"])
with col2:
    audio_only = st.checkbox("🎵 استخراج الصوت فقط")
    audio_fmt = st.selectbox("🎛️ صيغة الصوت المخرج:", list(AUDIO_CODEC_MAP.keys()), disabled=not audio_only)

st.markdown("#### ✂️ إعدادات قص المقطع (اختياري)")
col3, col4 = st.columns(2)
with col3:
    start_time = st.text_input("⏱️ زمن البداية (مثال: 0 أو 1:30):", value="0")
with col4:
    end_time = st.text_input("⏱️ زمن النهاية (مثال: 0 أو -1 للنهاية):", value="0")

subtitles = st.checkbox("ℹ️ تحميل الترجمة المرفقة")
sub_langs = st.text_input("🌐 رموز اللغات (مثل en,ar):", value="en,ar", disabled=not subtitles)

# --- تنفيذ العمليات ---
if st.button("🚀 البدء في معالجة وتحميل الملف"):
    if not video_url:
        st.error("يرجى إدخال رابط صالح أولاً.")
    else:
        with st.spinner("جاري الاتصال بالسيرفر وجلب بيانات الفيديو..."):
            
            # تم التعديل هنا: استخدام sys.executable لضمان قراءة الأداة
            meta_cmd = [sys.executable, '-m', 'yt_dlp', '-J', '--flat-playlist', video_url]
            res = run_quiet(meta_cmd)
            
            if res.returncode != 0:
                st.error("عذراً، فشل النظام في قراءة الرابط. تأكد من صحته ومن وجود ملف requirements.txt.")
            else:
                meta_data = json.loads(res.stdout)
                title = sanitize_filename(meta_data.get('title', 'downloaded_media'))
                
                st.info(f"🎬 تم العثور على: {title}")
                
                output_ext = 'mp3' if audio_only else 'mp4'
                temp_output = os.path.join(WORKDIR, f"temp_{title}.{output_ext}")
                final_output = os.path.join(WORKDIR, f"{title}.{output_ext}")
                
                dl_fmt = 'bestaudio/best' if audio_only else quality_format_chain(quality_selection)
                
                # تم التعديل هنا أيضاً
                dl_cmd = [sys.executable, '-m', 'yt_dlp', '-f', dl_fmt, '-o', temp_output, '--no-playlist', video_url]
                
                if not audio_only:
                    dl_cmd.extend(['--merge-output-format', 'mp4'])
                
                download_res = run_quiet(dl_cmd)
                
                if os.path.exists(temp_output):
                    if start_time != "0" or end_time != "0":
                        st.text("جاري قص المقطع المحدد وتعديل الأبعاد الزمنية...")
                        st_str = parse_time(start_time)
                        
                        if end_time == "-1" or end_time == "0":
                            cut_cmd = ['ffmpeg', '-y', '-ss', st_str, '-i', temp_output, '-c', 'copy', final_output]
                        else:
                            en_str = parse_time(end_time)
                            cut_cmd = ['ffmpeg', '-y', '-ss', st_str, '-to', en_str, '-i', temp_output, '-c', 'copy', final_output]
                        
                        run_quiet(cut_cmd)
                    else:
                        os.rename(temp_output, final_output)
                    
                    if os.path.exists(final_output):
                        st.success("✨ تمت العملية بنجاح! الملف جاهز للتحميل الآن.")
                        with open(final_output, "rb") as file:
                            st.download_button(
                                label="📥 اضغط هنا لحفظ الملف على جهازك",
                                data=file,
                                file_name=f"{title}.{output_ext}",
                                mime=f"video/{output_ext}" if not audio_only else f"audio/{output_ext}"
                            )
                        
                        shutil.rmtree(WORKDIR, ignore_errors=True)
                        os.makedirs(WORKDIR, exist_ok=True)
                else:
                    st.error("حدث خطأ أثناء معالجة أو دمج ملفات الفيديو المرجوة.")
