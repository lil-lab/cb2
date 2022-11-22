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
            innerDiv.style.padding = "20px";
            innerDiv.style.borderRadius = "5px";
            innerDiv.style.boxShadow = "0 0 10px rgba(0, 0, 0, 0.5)";
            innerDiv.style.textAlign = "center";
            innerDiv.style.border = "1px solid #ccc";
            modal.appendChild(innerDiv);
            innerDiv.appendChild(contents);
            document.body.appendChild(modal);
        }

        function createGoogleSigninModal(button_id) {
            // Import the roboto font.
            var roboto = document.createElement("link");
            roboto.setAttribute("rel", "stylesheet");
            roboto.setAttribute("href", "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700&display=swap");
            document.head.appendChild(roboto);
            var messages = []
            var message = document.createElement("p");
            message.innerHTML = "Please sign with Google to continue. We only use your account to connect to your game profile. No personal information is stored. The game data is used to improve the game and for natural language processing research at ";
            var cornellTechLink = document.createElement("a");
            cornellTechLink.setAttribute("href", "https://www.tech.cornell.edu/");
            cornellTechLink.setAttribute("target", "_blank");
            cornellTechLink.innerHTML = "Cornell University";
            cornellTechLink.style = "color: #0000EE; text-decoration: none; cursor: pointer;";
            message.appendChild(cornellTechLink);
            messages.push(message);
            var button = document.createElement("div");
            button.id = button_id;
            // Center the sign in with Google button by placing it within a div which is centered and of the same width.
            var buttonDiv = document.createElement("div");
            buttonDiv.style.display = "flex";
            buttonDiv.style.justifyContent = "center";
            buttonDiv.style.width = "100%";
            buttonDiv.appendChild(button);
            var modalContents = document.createElement("div");
            for (var i = 0; i < messages.length; i++) {
                // Set the font to roboto, fallback to sans-serif.
                messages[i].style.fontFamily = "Roboto, sans-serif";
                // Limit the width of the message.
                messages[i].style.maxWidth = "500px";
                // Add padding.
                messages[i].style.padding = "0px 10px 0 10px";
                // First message has zero margin. Subsequent messages have 10px margin on top.
                messages[i].style.margin = i == 0 ? "0" : "10px 0 0 0";
                modalContents.appendChild(messages[i]);
            }
            // Create a light grey separator between the message and the button. Span 90% of the width.
            var separator = document.createElement("hr");
            separator.style.width = "90%";
            separator.style.border = "0.5px solid #ccc";
            separator.style.margin = "15px auto 15px auto";
            modalContents.appendChild(separator);
            modalContents.appendChild(buttonDiv);
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