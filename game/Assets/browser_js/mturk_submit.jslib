mergeInto(LibraryManager.library, {
    // Function to submit mturk data to Amazon.
    SubmitMturk: function(game_data) { 
        var game_data = Pointer_stringify(game_data);
        var params = new URLSearchParams(window.location.search);
        var action = (new URL('mturk/externalSubmit', params.get('turkSubmitTo'))).href
        console.log(action);

        var htmlForm = document.createElement('form');
        htmlForm.action = action;
        htmlForm.method = 'post';

        // Add the assignment ID to the form.
        var assignmentIdInput = document.createElement("input");
        assignmentIdInput.setAttribute("type", "hidden");
        assignmentIdInput.setAttribute("name", "assignmentId");
        assignmentIdInput.setAttribute("value", params.get('assignmentId'));
        htmlForm.appendChild(assignmentIdInput);

        // Add the form data to the form.
        var formDataInput = document.createElement("input");
        formDataInput.setAttribute("type", "hidden");
        formDataInput.setAttribute("name", "game_data");
        formDataInput.setAttribute("value", game_data);
        htmlForm.appendChild(formDataInput);

        // Submit the form.
        document.body.appendChild(htmlForm);
        htmlForm.submit();
    },
});
