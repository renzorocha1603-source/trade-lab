        tab1, tab2 = st.tabs(["Login", "Create Account"])
        
        with tab1:
            if st.button("🔓 Unlock Dashboard", use_container_width=True, key="login_btn"):
                from auth import AuthSystem
                auth = AuthSystem()
                user = auth.login("renzochiara", password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("Incorrect password. Please try again.")
        
        with tab2:
            new_username = st.text_input("Choose a username", key="reg_user")
            new_password = st.text_input("Choose a password", type="password", key="reg_pass")
            new_name = st.text_input("Your name (optional)", key="reg_name")
            if st.button("✨ Create My Account", use_container_width=True, key="reg_btn"):
                if len(new_username) < 3:
                    st.error("Username must be at least 3 characters.")
                elif len(new_password) < 4:
                    st.error("Password must be at least 4 characters.")
                else:
                    from auth import AuthSystem
                    auth = AuthSystem()
                    user = auth.register(new_username, new_password, new_name)
                    if user:
                        st.success(f"Account created! Welcome, {new_name or new_username}!")
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Username already taken. Try a different one.")