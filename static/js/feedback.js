$(document).ready(function () {
    $(document).on('click', '#saveRemarksBtnUnique', function () {
        const remarks = $('#remarksUnique').val().trim();
        const feedback = 'dislike';
        const files = Array.from($('#docUploadUnique')[0].files);
        const message_id = $('#b_message_id').val(); 

        if (!message_id || !remarks) {
            alert('User query, bot response, and remarks are required.');
            return;
        }

        const formData = new FormData();
        formData.append('message_id', message_id);
        formData.append('remarks', remarks);
        formData.append('feedback', feedback);

        files.forEach(file => {
            formData.append('files[]', file); 
        });

        for (let [key, value] of formData.entries()) {
            if (key === 'files[]') {
                console.log(`${key}: ${value.name}`); 
            } else {
                console.log(`${key}: ${value}`); 
            }
        }

        $.ajax({
            url: '/submit_feedback',
            type: 'POST',
            data: formData,
            processData: false,  
            contentType: false,  
            success: function (response) {
                if (response.message === "Feedback submitted successfully") {
                    $('#remarksUnique').val(''); 
                    $('#docUploadUnique').val(''); 
                    $('.close').click(); 
                    alert('Feedback submitted successfully!');
                } else {
                    alert('Error submitting feedback. Please try again.');
                }
            },
            error: function () {
                alert('An error occurred while submitting feedback.');
            }
        });
    });
});
