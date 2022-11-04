mergeInto(LibraryManager.library, {
    LoginGoogleOneTap: function(client_id) { 
        // Automatically loads the Google One Tap API and waits for the user to
        // authenticate. Calls back into Unity with the user's unique ID.
        var script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        document.head.appendChild(script);

        function handleCredentialResponse(response) {
            // Pass the JWT back to Unity.
            const jwtToken = response.credential;
            MyGameInstance.SendMessage("GoogleOneTap", "OnLoginSuccess", jwtToken);
        }

        // From documentation here:
        // https://developers.google.com/identity/gsi/web/reference/js-reference
        window.onGoogleLibraryLoad = () => {
              google.accounts.id.initialize({
                client_id: client_id,
                callback: handleCredentialResponse
              });
              google.accounts.id.prompt();
        };
    },
    CancelGoogleOneTap: function(filename, data) {
        if (google !== undefined) {
            google.accounts.id.cancel();
        }
    }
);