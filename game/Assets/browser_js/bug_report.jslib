mergeInto(LibraryManager.library, {
    // Function to download data to a file. Works by embedding the data in a link
    // and then triggering a click event on it.
    DownloadJson: function(filename, data) { 
        var filename = Pointer_stringify(filename);
        var data = Pointer_stringify(data);
        var file = new Blob([data], {type: 'application/json'});

        // IE 10+
        if (window.navigator.msSaveOrOpenBlob) {
            window.navigator.msSaveOrOpenBlob(file, filename);
            return;
        }

        // Other browsers.
        var a = document.createElement("a");
        var url = URL.createObjectURL(file);
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        setTimeout(function() {
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);  
        }, 0); 
    
    },
    LogToConsole: function(log) {
        var log = Pointer_stringify(log);
        console.log(log);
    }
});
