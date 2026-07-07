import streamlit as st
import requests
import uuid
import base64 
import hashlib

BACKEND_URL = "http://localhost:8000"

st.set_page_config(
    page_title="AI Assistant",
    page_icon="🤖",
    layout="wide"
)

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())

if "email" not in st.session_state:
    st.session_state.email = ""

if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None

if "audio_widget_key" not in st.session_state:
    st.session_state.audio_widget_key = 0

if "services_connected" not in st.session_state:
    st.session_state.services_connected = False



def signup(email, password):
    try:
        response = requests.post(
            f"{BACKEND_URL}/signup",
            json={
                "email": email,
                "password": password
            },
            timeout=30
        )
        return response
    except Exception as e:
        st.error(str(e))
        return None

def login(email, password):
    try:
        response = requests.post(
            f"{BACKEND_URL}/login",
            json={
                "email": email,
                "password": password
            },
            timeout=30
        )
        return response
    except Exception as e:
        st.error(str(e))
        return None

def send_message(message):

    response = requests.post(
        f"{BACKEND_URL}/chat",
        json={
            "user_id": st.session_state.user_id,
            "thread_id": st.session_state.thread_id,
            "message": message
        },
        timeout=120
    )
    return response

def connect_services():
    response = requests.post(
        f"{BACKEND_URL}/connect/services",
        json={
            "user_id": st.session_state.user_id
        }
    )
    return response

def create_new_thread(user_id, thread_id, title="New Conversation"):
    try:
        response = requests.post(
            f"{BACKEND_URL}/threads",
            json={
                "user_id": user_id,
                "thread_id": thread_id,
                "title": title
            },
            timeout=10
        )
        return response
    except Exception as e:
        st.sidebar.error(f"Failed to create thread: {e}")
        return None

def fetch_user_threads(user_id):
    try:
        response = requests.get(
            f"{BACKEND_URL}/threads/{user_id}",
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("threads", [])
        return []
    except Exception as e:
        st.sidebar.error(f"Failed to fetch threads: {e}")
        return []

def fetch_chat_history(thread_id):
    print("Fetching history for:", thread_id)
    try:
        response = requests.get(
            f"{BACKEND_URL}/chat/history/{thread_id}",
            timeout=15
        )
        if response.status_code == 200:
            return response.json().get("messages", [])
        return []
    except Exception as e:
        st.error(f"Failed to load history: {e}")
        return []
    
def check_connection_status(user_id):
    try:
        response = requests.get(
            f"{BACKEND_URL}/user/{user_id}/connection-status",
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("is_connected", False)
        return False
    except Exception as e:
        st.error(f"Failed to check connection status: {e}")
        return False

def confirm_user_connection(user_id):
    try:
        response = requests.post(
            f"{BACKEND_URL}/user/{user_id}/confirm-connection",
            timeout=10
        )
        if response.status_code == 200:
            return response.json().get("success", False)
        return False
    except Exception as e:
        st.error(f"Failed to confirm connection: {e}")
        return False





if not st.session_state.logged_in:

    st.title("AI Assistant")

    tab1, tab2 = st.tabs(["Login", "Signup"])

    with tab1:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login"):
            res = login(email, password)
            if res is not None:
                if res.status_code == 200:
                    data = res.json()
                    st.session_state.logged_in = True
                    st.session_state.user_id = data["user_id"]
                    st.session_state.email = email
                    st.session_state.services_connected = check_connection_status(data["user_id"])
                    st.success("Login Successful")
                    create_new_thread(st.session_state.user_id, st.session_state.thread_id , title="Empty Chat")
                    st.rerun()
                else:
                    st.error(res.json()["detail"])

    with tab2:
        st.subheader("Signup")
        email = st.text_input("Email", key="signup_email")
        password = st.text_input("Password", type="password", key="signup_password")

        if st.button("Create Account"):
            res = signup(email, password)
            if res is not None:
                if res.status_code == 200:
                    st.success("Account created successfully! Please check your email and verify your account before logging in.")
                else:
                    st.error(res.json()["detail"])

elif not st.session_state.services_connected:
    st.title("Welcome! Let's get you set up.")
    st.write("To use the AI Assistant, please connect your Google Workspace.")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("Connect Gmail & Calendar", use_container_width=True):
            with st.spinner("Generating links..."):
                try:
                    res = connect_services()
                    if res.status_code == 200:
                        data = res.json()
                        st.success("Please click the links below to authorize in a new tab:")
                        st.markdown(f"🔗 **[Connect Gmail]({data['gmail_url']})**")
                        st.markdown(f"🔗 **[Connect Calendar]({data['calendar_url']})**")
                        st.markdown(f"🔗 **[Connect Drive]({data['drive_url']})**")
                        st.info("Once you have authorized both, click the verify button below.")
                    else:
                        st.error(res.json().get("detail", "Error generating links."))
                except Exception as e:
                    st.error(str(e))
                    
    with col2:
        st.write("Already finished authorizing?")
        if st.button("Verify Connection & Continue", type="primary", use_container_width=True):
            with st.spinner("Confirming setup..."):
                
                update_success = confirm_user_connection(st.session_state.user_id)
                
                if update_success:
                    st.session_state.services_connected = True
                    st.success("Successfully connected! Redirecting...")
                    import time
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("We couldn't verify your connection. Please try again.")



else:

    with st.sidebar:
        st.write(f"Logged in as")
        st.write(st.session_state.email)

        st.divider()
        st.subheader("Conversations")

        if st.button("➕ New Chat", use_container_width=True):
            print("=" * 50)
            print("NEW CHAT CLICKED")
            print("Old:", st.session_state.thread_id)

            new_id = str(uuid.uuid4())
            print("New:", new_id)
            
            create_new_thread(st.session_state.user_id, new_id , title="Empty Chat")
            
            st.session_state.thread_id = new_id
            st.session_state.messages = []
            st.rerun()

        user_threads = fetch_user_threads(st.session_state.user_id)
        
        if user_threads:
            thread_options = {}

            for i, t in enumerate(user_threads):
                label = f"{t['title']} ({t['created_at'][:10]}) #{i+1}"
                thread_options[label] = t["thread_id"]
            
            current_index = 0
            thread_ids_list = list(thread_options.values())
            if st.session_state.thread_id in thread_ids_list:
                current_index = thread_ids_list.index(st.session_state.thread_id)

            selected_thread_label = st.selectbox(
                "Previous Chats",
                options=list(thread_options.keys()),
                index=current_index
            )

            selected_thread_id = thread_options[selected_thread_label]

            if selected_thread_id != st.session_state.thread_id:
                with st.spinner("Loading conversation..."):
                    st.session_state.thread_id = selected_thread_id
                    st.session_state.messages = fetch_chat_history(selected_thread_id)
                st.rerun()

        st.divider()
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()


    st.title("AI Assistant")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            if message.get("audio_reply"):
                should_autoplay = message.get("autoplay", False)
                st.audio(message["audio_reply"], autoplay=should_autoplay)
                
                if should_autoplay:
                    message["autoplay"] = False

    audio_val = st.audio_input("Record your message..." , key=f"audio_input_{st.session_state.audio_widget_key}")

    print("=" * 50)
    print("audio_val exists:", audio_val is not None)

    process_audio = False

    if audio_val:
        audio_bytes = audio_val.getvalue()

        current_audio_hash = hashlib.sha256(audio_bytes).hexdigest()

        if current_audio_hash != st.session_state.last_audio_hash:
            st.session_state.last_audio_hash = current_audio_hash
            process_audio = True
            print("Sending audio...")
        else:
            print("Duplicate audio ignored.")

    if process_audio:
        
        audio_b64 = base64.b64encode(audio_val.getvalue()).decode("utf-8") 

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = send_message(audio_b64)

                    if response.status_code == 200:
                        data = response.json()
                        user_text = data.get("user_text")
                        reply = data.get("reply", "")
                        audio_reply = data.get("audio_reply", None)
                    else:
                        reply = response.json().get("detail", "Error occurred")
                        audio_reply = None

                except Exception as e:
                    reply = str(e)
                    audio_reply = None

                st.session_state.messages.append(
                    {
                        "role": "user",
                        "content": user_text
                    }
                )

                with st.chat_message("user"):
                    st.markdown(user_text)
                    st.audio(audio_val)
                st.markdown(reply)
        
        for msg in st.session_state.messages:
            if "audio_reply" in msg:
                msg["audio_reply"] = None

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": reply,
                "audio_reply": audio_reply,
                "autoplay": True
            }
        )
        st.session_state.audio_widget_key += 1
        st.rerun()