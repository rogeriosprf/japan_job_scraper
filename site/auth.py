# site/auth.py
import streamlit as st


def check_password() -> bool:
    """
    Gate simples por senha única — uso pessoal, um usuário só, sem tabela
    de usuários nem OAuth. Se já autenticado nessa sessão, retorna True
    direto. Senão, mostra o formulário e para a execução da página com
    st.stop() até a senha certa ser digitada.
    """

    if st.session_state.get("authenticated"):
        return True

    st.title("🔒 Login")
    password = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        if password == st.secrets.get("SITE_PASSWORD"):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")

    st.stop()
