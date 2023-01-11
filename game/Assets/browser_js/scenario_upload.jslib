mergeInto(LibraryManager.library, {
    // Function to ask the user for a file to upload.
    PromptUpload: function() { 
        function on_file_change(evt) {
            const fileList = this.files;

            if (fileList.length == 0) {
                console.log("No file selected.");
                return;
            }

            if (fileList.length > 1) {
                console.log("Multiple files selected. Choosing first.");
            }

            const file = fileList[0];
            console.log("Selected file: " + file.name);
            console.log("Selected file size: " + file.size);
            console.log("Selected file type: " + file.type);

            console.log("Reading file...");
            const reader = new FileReader();
            reader.onload = function(e) { 
                const content = e.target.result;
                if ( (content === undefined) || (content === null) ) {
                    console.log("File content is empty.");
                    return;
                }
                SendMessage("InGameMenuHandler", "OnFileReady", content);
            }
            reader.readAsText(file);
        }
        var htmlForm = document.createElement('input');
        htmlForm.type = 'file';
        htmlForm.onchange = on_file_change;
        htmlForm.click();
    },
});
