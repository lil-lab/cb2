mergeInto(LibraryManager.library, {
    // Function to ask the user for a file to upload.
    PromptUpload: function() { 
        function on_file_change(event) {
            // Pass the JWT back to Unity.
            const content = event.target.result;
            SendMessage("UploadScenarioHandler", "OnFileReady", content);
        }

        var htmlForm = document.createElement('input');
        htmlForm.type = 'file';
        htmlForm.onchange = on_file_change;
        htmlForm.click();
    },
});
