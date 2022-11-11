mergeInto(LibraryManager.library, {
    LoginGoogleOneTap: function(client_id) { 
        // Automatically loads the Google One Tap API and waits for the user to
        // authenticate. Calls back into Unity with the user's unique ID.
        var client_id = Pointer_stringify(client_id);
        var script = document.createElement("script");
        script.src = "https://accounts.google.com/gsi/client";
        document.head.appendChild(script);
        console.log("Loading Google One Tap API from jslib.");

        function handleCredentialResponse(response) {
            // Pass the JWT back to Unity.
            const jwtToken = response.credential;
            SendMessage("GoogleOneTap", "OnLogin", jwtToken);
        }

        // From documentation here:
        // https://developers.google.com/identity/gsi/web/reference/js-reference
        window.onGoogleLibraryLoad = function () {
              google.accounts.id.initialize({
                client_id: client_id,
                callback: handleCredentialResponse
              });
              google.accounts.id.prompt();
        };
    },
    CancelGoogleOneTap: function() {
        if (google !== undefined) {
            google.accounts.id.cancel();
        }
    }
});