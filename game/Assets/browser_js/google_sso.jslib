mergeInto(LibraryManager.library, {
    LoginGoogleOneTap: function(client_id) { 
        console.log("Loading Google One Tap API from jslib.");

        function createModal(modal_id, contents) {
            // Create a modal to display errors.
            var modal = document.createElement("div");
            modal.setAttribute("id", modal_id);
            modal.setAttribute("class", "modal");
            // Change the div style.
            modal.style.position = "absolute";
            modal.style.top = "0";
            modal.style.left = "0";
            modal.style.width = "100%";
            modal.style.height = "100%";
            modal.style.backgroundColor = "rgba(0, 0, 0, 0.5)";
            modal.style.display = "flex";
            modal.style.alignItems = "center";
            modal.style.justifyContent = "center";
            modal.style.zIndex = "1000";
            // Blur the unity container.
            var unity_container = document.getElementById("unity-container");
            unity_container.style.filter = "blur(5px)";
            // Create an inner div.
            var innerDiv = document.createElement("div");
            innerDiv.style.backgroundColor = "white";
            innerDiv.style.padding = "10px";
            innerDiv.style.borderRadius = "10px";
            innerDiv.style.boxShadow = "0 0 10px rgba(0, 0, 0, 0.5)";
            innerDiv.style.textAlign = "center";
            modal.appendChild(innerDiv);
            innerDiv.appendChild(contents);
            document.body.appendChild(modal);
        }

        function createGoogleSigninModal(button_id) {
            var message = document.createElement("p");
            message.innerHTML = "Please sign in with Google to continue. We only use your account to uniquely identify you and track your performance. No personal information is stored.";
            // Set the font to a nice sans-serif font.
            message.style.fontFamily = "sans-serif";
            // Limit the width of the message.
            message.style.maxWidth = "500px";
            // Add a light grey background to the message.
            message.style.backgroundColor = "#eee";
            // Add padding.
            message.style.padding = "10px";
            // Round corners.
            message.style.borderRadius = "10px";
            var button = document.createElement("div");
            button.id = button_id;
            // Center the button with some injected CSS. Create a style tag.
            // Make all children of the button margin: auto;
            // Use # button_id > * { margin: auto; }
            var style = document.createElement("style");
            style.innerHTML = "#" + button_id + " > * { margin: auto; }";
            document.head.appendChild(style);
            var modalContents = document.createElement("div");
            modalContents.appendChild(message);
            modalContents.appendChild(button);
            createModal("google-signin-modal", modalContents);
        }

        var google_signin_button_id = "google-signin-button";
        createGoogleSigninModal(google_signin_button_id);

        // Automatically loads the Google One Tap API and waits for the user to
        // authenticate. Calls back into Unity with the user's unique ID.
        var client_id = Pointer_stringify(client_id);
        var script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        document.head.appendChild(script);

        function handleCredentialResponse(response) {
            // Pass the JWT back to Unity.
            const jwtToken = response.credential;
            SendMessage("GoogleOneTapLogin", "OnLogin", jwtToken);
            // Delete the modal window.
            document.body.removeChild(document.getElementById("google-signin-modal"));
            // Unblur the unity container.
            var unity_container = document.getElementById("unity-container");
            unity_container.style.filter = "none";
        }

        // From documentation here:
        // https://developers.google.com/identity/gsi/web/reference/js-reference
        window.onGoogleLibraryLoad = function () {
              google.accounts.id.initialize({
                client_id: client_id,
                auto_select: true,
                callback: handleCredentialResponse
              });
              google.accounts.id.renderButton(
                document.getElementById(google_signin_button_id),
                { 
                  theme: "outline",
                  size: "large",
                  type: "standard",
                  theme: "filled_blue",
                  text: "continue_with",
                  shape: "pill",
                }
              );
              google.accounts.id.prompt();
        };
    },
    CancelGoogleOneTap: function() {
        if (google !== undefined) {
            google.accounts.id.cancel();
        }
        // Delete the modal window.
        document.body.removeChild(document.getElementById("google-signin-modal"));

        // Unblur the unity container.
        var unity_container = document.getElementById("unity-container");
        unity_container.style.filter = "none";
    },
    LogOutGoogleOneTap: function() {
        if (google !== undefined) {
            google.accounts.id.disableAutoSelect();
        }
    }
});