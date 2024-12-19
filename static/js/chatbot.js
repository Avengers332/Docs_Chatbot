$(document).ready(function () {

  $('[data-toggle="tooltip"]').tooltip();
  
    const maxLength = 500; 

    $('#sendBtn').on('click', function() {
      let userMessage = $('#userMessage').val().trim();

      if (userMessage.length > maxLength) {
        $('#errorIndicator').text(`Your query exceeds ${maxLength} characters. Please shorten it.`).removeClass('d-none');
        return;
      } else if (!userMessage) {
        $('#errorIndicator').text('Please enter a message.').removeClass('d-none');
        return;
      }

      $('#errorIndicator').addClass('d-none');

      // Proceed with sending the message
      if (!$('#initial_heading').hasClass('d-none')) {
           $('#initial_heading').fadeOut().addClass('d-none');
      }
      if($('#chatBox').css('display') === 'none'){
        $('#chatBox').css('display', 'block');  
        $('#chatBox').removeClass('d-none');
      }
      addMessage('user', userMessage);
      $('#userMessage').val(''); 
      // Call the API to get the bot's response
      callBotAPI(userMessage);
    });

    $('#userMessage').on('input', function() {
      $('#errorIndicator').addClass('d-none');
    });

    $('#userMessage').on('keydown', function (e) {
      if (e.key === 'Enter') {
        $('#sendBtn').click();
      }
    });
    function addMessage(sender, text, messageId = null) {
      const isBot = sender === 'bot'; // Check if the message is from the bot
      let messageIdAttr = '';

      // Add data-messageId attribute only if it's a bot message and a botResponse is provided
      if (isBot && messageId ) {
          messageIdAttr = ` data-messageId="${messageId}"`;
      }
      // Construct the message HTML
      const messageHTML = `
          <div class="message ${sender}">
              <div class="text" ${messageIdAttr}>${text}</div>
              ${isBot ? `
              <div class="message-actions" style="display:block;">
                  <i class="bi bi-copy mx-1 mb-5 copyBtn" id="copyBtn" data-toggle="tooltip" data-bs-placement="bottom" data-original-title="Copy" style="display:;"><span class="copyBtnText" id="copyBtnText" style="font-family:Poppins, Arial, sans-serif;"></span></i>
                  <i class="bi bi-hand-thumbs-up mx-1 likeBtn" data-toggle="tooltip" data-bs-placement="bottom" data-original-title="Like"></i>
                  <i class="bi bi-hand-thumbs-down mx-1 dislikeBtn" data-toggle="tooltip" data-bs-placement="bottom" data-original-title="Dislike" data-bs-toggle="modal" data-bs-target="#dislikeModal"></i>
              </div>` : ''}
          </div>
      `;
  
      // Append the message to the chatbox
      $('#chatBox').append(messageHTML);
      $('#chatBox').animate({ scrollTop: $('#chatBox').prop("scrollHeight") }, 500);
  
      // If it's a bot message, handle actions and adjust positioning
      if (isBot) {
          const lastMessage = $('#chatBox .message.bot').last();
          
          // Fade in message actions
          lastMessage.find('.message-actions').fadeIn(500);
  
          // Initialize tooltips
          $('[data-toggle="tooltip"]').tooltip();
  
          // Adjust message actions' position
          // adjustMessageActions(lastMessage);
          setTimeout(() => adjustMessageActions(lastMessage), 10);
      }
  }

  function typingEffect(botResponse) {
    // Extract the text and message ID
    var text = botResponse.response;
    var message_id = botResponse.bot_message_id;

    // Create the typing message element
    const typingMsg = $(`<div class="message bot"><div class="text typing" data-messageId="${message_id}"></div>
      <div class="message-actions" style="display:none;">
          <i class="bi bi-copy mx-1 mb-5 copyBtn" id="copyBtn" data-toggle="tooltip" data-bs-placement="bottom" data-original-title="Copy" style="display:;"><span class="copyBtnText" id="copyBtnText" style="font-family:Poppins, Arial, sans-serif;"></span></i>
          <i class="bi bi-hand-thumbs-up mx-1 likeBtn" data-toggle="tooltip" data-bs-placement="bottom" data-original-title="Like"></i>
          <i class="bi bi-hand-thumbs-down mx-1 dislikeBtn" data-toggle="tooltip" data-bs-placement="bottom" data-original-title="Dislike" data-bs-toggle="modal" data-bs-target="#dislikeModal"></i>
      </div></div>`);
    $('#chatBox').append(typingMsg);
    const botMessage = $('#chatBox .message.bot').last();
   
    $('#chatBox').animate({ scrollTop: $('#chatBox').prop("scrollHeight") }, 500);

    let i = 0;
    const typingInterval = setInterval(() => {
      
        typingMsg.find('.text').append(text[i]);
        i++;
        if (i >= text.length) {
          
            clearInterval(typingInterval);
            typingMsg.find('.text').removeClass('typing');
            setTimeout(() => adjustMessageActions(botMessage), 10);
            // Find the nearest .message-actions and remove display:none style
            botMessage.find('.message-actions').css('display', 'block');
            // Initialize tooltips
            $('[data-toggle="tooltip"]').tooltip();

        }
    }, 12);
}

    // Fetch chat history on page load
fetchChatHistory();

function fetchChatHistory() {
  $.ajax({
      url: '/get_history',
      method: 'GET',
      success: function (data) {
          if (data.active_chat_history && Array.isArray(data.active_chat_history) && data.active_chat_history.length > 0) {
              const chatHistory = data.active_chat_history[0]; // Get the first conversation
              const messages = chatHistory.messages; // Extract messages array

              $('#chatBox').empty();
              $('#query-space').show();
              $('#new_chat').removeClass('d-none')
              // Add each message to the chat box
              messages.forEach(message => {
                  const sender = message.sender === 'bot' ? 'bot' : 'user';
                  const content = message.content; // Use 'content' from the response
                  const messageId = message.message_id; 
                  const feedback = message.feedback.feedback; // Get the feedback for the message

                  // Add the message to the chat
                  addMessage(sender, content, messageId);

                  // Check the feedback and set the button states
                  const $message = $('#chatBox .message').last();

                  if (sender === 'bot') {
                      const $likeBtn = $message.find('.likeBtn');
                      const $dislikeBtn = $message.find('.dislikeBtn');

                      if (feedback === 'like') {
                          $likeBtn.addClass('liked');
                          updateTooltip($likeBtn, 'Liked');
                      } else if (feedback === 'dislike') {
                          $dislikeBtn.addClass('disliked');
                          updateTooltip($dislikeBtn, 'Disliked');
                      }
                  }
              });
              
              // Scroll to the bottom after chat history is loaded
              $('#chatBox').animate({ scrollTop: $('#chatBox')[0].scrollHeight }, 10);

              // Update UI visibility
              $('#initial_heading').fadeOut().addClass('d-none');
              $('#chatBox').removeClass('d-none');
          } else {
              console.error("No active chat history found:", data);
          }
      },
      error: function (xhr, status, error) {
          console.error("Error fetching chat history:", error);
      }
  });
}

// Function to view conversation details
function viewConversationDetails(conversationId) {
 
  // Dynamically create the loader and append it to the body (or specific container)
  const loader = $('<div>', { id: 'loadingSpinner', class: 'text-center' })
    .append(
      $('<div>', { class: 'spinner-border text-primary', role: 'status' })
        .append($('<span>', { class: 'sr-only', text: 'Loading...' }))
    );
  $('#chatbox').append(loader);  // You can change this to a specific container if needed

  $.ajax({
      url: '/get_conversation_details',
      method: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ conversation_id: conversationId }),
      success: function (response) {
          if (response.status === 'success') {
              const { messages, feedbacks } = response;
             
              $('#query-space').hide();
              // Clear the chat box
              $('#chatBox').empty();

              // Add each message to the chat box
              messages.forEach(message => {
                  const sender = message.sender === 'bot' ? 'bot' : 'user';
                  const content = message.content;
                  const messageId = message.message_id || null;

                  // Find feedback for this message (if any)
                  const feedbackData = feedbacks.find(fb => fb.message_content === content);
                  const feedback = feedbackData ? feedbackData.feedback : null;

                  // Add the message to the chat
                  addMessage(sender, content, messageId);

                  // Handle feedback button states for bot messages
                  const $message = $('#chatBox .message').last();
                  if (sender === 'bot') {
                      const $likeBtn = $message.find('.likeBtn');
                      const $dislikeBtn = $message.find('.dislikeBtn');

                      if (feedback === 'like') {
                          $likeBtn.addClass('liked');
                          updateTooltip($likeBtn, 'Liked');
                      } else if (feedback === 'dislike') {
                          $dislikeBtn.addClass('disliked');
                          updateTooltip($dislikeBtn, 'Disliked');
                      }
                  }
              });

              // Scroll to the bottom of the chat box
              $('#chatBox').animate({ scrollTop: $('#chatBox').prop('scrollHeight') }, 10);

              const $chatBox = $('#chatBox');
              if ($chatBox.hasClass('d-none') || $chatBox.css('display') === 'none') {
                  $chatBox.removeClass('d-none').fadeIn();
              }

          } else {
              console.error('Failed to load conversation details:', response.message);
          }

          // Remove the loader after the request is completed
          $('#loadingSpinner').remove();
      },
      error: function (xhr) {
          console.error('Error fetching conversation details:', xhr.responseJSON.message);
          
          // Remove the loader in case of error as well
          $('#loadingSpinner').remove();
      }
  });
}


// Generic function to handle AJAX for both like and dislike
function submitFeedback(messageId, feedbackType) {
  
  const data = {
      message_id: messageId,
      feedback: feedbackType
  };

  $.ajax({
      url: '/response_feedback',
      type: 'POST',
      contentType: 'application/json',
      data: JSON.stringify(data),
      success: function (response) {
          if (response.status === 'success') {
              return true
          } else {
             return false
          }
      },
      error: function (xhr) {
          console.error('Error occurred:', xhr.responseText);
          alert('An error occurred while submitting your feedback. Please try again later.');
      }
  });
}
    
    $(document).on('click','.view-conversation', function(){
      var conversation_id = $(this).data('id');
      $('.dropdown-menu').removeClass('show');
      const $initialHeading = $('#initial_heading');
      if (!$initialHeading.hasClass('d-none') || $initialHeading.css('display') !== 'none') {
        $initialHeading.fadeOut(() => $initialHeading.addClass('d-none'));
      }
      viewConversationDetails(conversation_id)
      $('#back_2_chat').removeClass('d-none')
      $('#new_chat').addClass('d-none')
    })
    $(document).on('click','#back_2_chat', function(){
      fetchChatHistory();
      location.reload()
    })
    
    // Like button click handler
    $(document).on('click', '.likeBtn', function () {
      console.log('likeBtn');
      const $likeBtn = $(this);
      const $dislikeBtn = $likeBtn.closest('.message').find('.dislikeBtn');
      const like_message_id = $likeBtn.closest('.message').find('.text').data('messageid');
      
      // Toggle the like button state
      if ($likeBtn.hasClass('liked')) {
          $likeBtn.removeClass('liked bi-hand-thumbs-up-fill').addClass('bi-hand-thumbs-up');
          updateTooltip($likeBtn, 'Like');
          submitFeedback(like_message_id, 'none');
      } else {
          $likeBtn.addClass('liked bi-hand-thumbs-up-fill').removeClass('bi-hand-thumbs-up');
          updateTooltip($likeBtn, 'Liked');
          submitFeedback(like_message_id, 'like');
          // Ensure dislike button is reset
          $dislikeBtn.removeClass('disliked bi-hand-thumbs-down-fill').addClass('bi-hand-thumbs-down');
          updateTooltip($dislikeBtn, 'Dislike');
      }
    });


    // Dislike button click handler
    $(document).on('click', '.dislikeBtn', function () {
      const $dislikeBtn = $(this);
      const $likeBtn = $dislikeBtn.closest('.message').find('.likeBtn');
      const $message = $dislikeBtn.closest('.message'); 
      const dislike_message_id = $likeBtn.closest('.message').find('.text').data('messageid');
      const botResponse = $message.find('.text').text(); // Get the bot response text for this message
      // Check the current state before toggling
      const isDisliked = $dislikeBtn.hasClass('disliked');

      // Toggle the dislike button state
      if (isDisliked) {
          $dislikeBtn.removeClass('disliked bi-hand-thumbs-down-fill').addClass('bi-hand-thumbs-down');
          updateTooltip($dislikeBtn, 'Dislike');
          submitFeedback(dislike_message_id, 'none');
      } else {
          $dislikeBtn.addClass('disliked bi-hand-thumbs-down-fill').removeClass('bi-hand-thumbs-down');
          updateTooltip($dislikeBtn, 'Disliked');
          submitFeedback(dislike_message_id, 'dislike');
          // Ensure like button is reset
          $likeBtn.removeClass('liked bi-hand-thumbs-up-fill').addClass('bi-hand-thumbs-up');
          updateTooltip($likeBtn, 'Like');
      }

      // Show the modal only if the button is newly disliked
      if (!isDisliked) {
          const userQuery = $('#chatBox .message.user:last .text').text(); // Assume last user message is related
          $('#userQueryUnique').text(userQuery);
          $('#botResponseUnique').text(botResponse); // Use the specific bot response for this button
          $('#remarksUnique').val('');

          // Pass the message_id to the modal using a custom data attribute
          const modalElement = document.getElementById('dislikeModal');

          // Optionally, store the message_id in a hidden input field in the modal
          $('#dislikeModal').find('input[name="message_id"]').val(dislike_message_id);

          // Show the modal
          const myModal = new bootstrap.Modal(modalElement);
          myModal.show();
      }
    });

    // Copy button click handler
    $(document).on('click', '#copyBtn', function () {
      const $copyBtn = $(this);
      
      const textToCopy = $copyBtn.closest('.message').find('.text').contents().filter(function() {
          return this.nodeType === 3;
      }).text();

      if (navigator.clipboard) {
          navigator.clipboard.writeText(textToCopy).then(() => {
              updateTooltip($copyBtn, 'Copied');
          }).catch(err => {
              console.error('Failed to copy: ', err);
          });
      } else {
          const tempTextArea = document.createElement('textarea');
          tempTextArea.value = textToCopy;
          document.body.appendChild(tempTextArea);

          tempTextArea.select();
          try {
              document.execCommand('copy');
              updateTooltip($copyBtn, 'Copied');
          } catch (err) {
              console.error('Fallback: Failed to copy', err);
          }
          document.body.removeChild(tempTextArea);
      }
    });

    // Function to update tooltip text and reinitialize
    function updateTooltip($element, newText) {
     
      const $btn = $element; 

      if ($btn.hasClass('copyBtn')) {
          // $btn.closest('.message').find('.copyBtnText').text('Copied');
          $btn.closest('.message').find('.copyBtn').removeClass('bi-copy').addClass('bi-check');
      }

      $btn.attr('title', newText);
      $btn.tooltip('dispose').tooltip();

      setTimeout(() => {
          if ($btn.hasClass('copyBtn')) {
              $btn.closest('.message').find('.copyBtn').removeClass('bi-check').addClass('bi-copy');
              // $btn.closest('.message').find('.copyBtnText').text(' Copy');
              $btn.attr('title', 'Copy').tooltip('dispose').tooltip();
          } else if ($btn.hasClass('likeBtn')) {
              $btn.removeClass('bi-hand-thumbs-up-fill').addClass('bi-hand-thumbs-up');
              $btn.attr('title', 'Like').tooltip('dispose').tooltip();
          } else if ($btn.hasClass('dislikeBtn')) {
              $btn.removeClass('bi-hand-thumbs-down-fill').addClass('bi-hand-thumbs-down');
              $btn.attr('title', 'Dislike').tooltip('dispose').tooltip();
          }
      }, 3000);
    }
    
    // Read Aloud button click handler
    $(document).on('click', '.readAloudBtn', function () {
      const $icon = $(this); // Store the icon element
      const textToRead = $icon.closest('.message').find('.text').text();
  
      if (!textToRead) {
          console.log('No text to read aloud.');
          return;
      }
  
      const speech = new SpeechSynthesisUtterance(textToRead);
      speech.lang = 'en-US';
      speech.rate = 1;
      speech.pitch = 1;
  
      // Handle speech pause
      speech.onpause = function () {
          console.log('Speech paused');
          $icon.removeClass('bi-stop-circle').addClass('bi-volume-up'); // Reset to volume-up icon
      };
  
      // Handle when speech ends
      speech.onend = function () {
          console.log('Speech has finished.');
          $icon.removeClass('bi-stop-circle').addClass('bi-volume-up'); // Reset to volume-up icon
          $icon.prop('disabled', false); // Re-enable the button
      };
  
      // // If the icon is in stop state (speech is currently playing), stop the speech and reset the icon
      // if ($icon.hasClass('bi-stop-circle')) {
      //     console.log('Stopping speech.');
      //     window.speechSynthesis.cancel(); // Stop the speech immediately
      //     $icon.removeClass('bi-stop-circle').addClass('bi-volume-up'); // Change to volume-up icon
      //     return;
      // }
  
      // If speech is already speaking, cancel the current speech
      if (window.speechSynthesis.speaking) {
          console.log('Already speaking, stopping speech.');
          window.speechSynthesis.cancel(); // Cancel ongoing speech
          $icon.removeClass('bi-stop-circle').addClass('bi-volume-up'); // Reset to volume-up icon
          return;
      }
  
      // Disable the icon while speech is in progress
      $icon.prop('disabled', true);
  
      // Start reading the text aloud
      window.speechSynthesis.speak(speech);
  
      // Change the icon to stop icon while speech is being read aloud
      $icon.removeClass('bi-volume-up').addClass('bi-stop-circle');
    });

    $(document).ready(function () {
      var $uploadedFilesContainer = $('#uploadedFilesContainer');
      var allFiles = []; 
      $uploadedFilesContainer.hide();

      $('#docUploadUnique').on('change', function () {
          var $fileListContainer = $('#fileListContainer');
          var duplicateFileNames = [];
          var newFiles = Array.from(this.files); 

          newFiles.forEach(function (file) {
              var fileName = file.name;
              if (!allFiles.some(existingFile => existingFile.name === fileName)) {
                  allFiles.push(file);
              } else {
                  duplicateFileNames.push(fileName);
              }
          });

          if (duplicateFileNames.length > 0) {
              var message = `Duplicate file(s) detected: ${duplicateFileNames.join(', ')}. Please choose unique files.`;
              $('#fileErrorContainer').text(message).fadeIn();
              setTimeout(function () {
                  $('#fileErrorContainer').fadeOut();
              }, 3000);
          } else {
              $('#fileErrorContainer').hide();
          }

          var dataTransfer = new DataTransfer();
          allFiles.forEach(function (file) {
              dataTransfer.items.add(file);
          });
          document.getElementById('docUploadUnique').files = dataTransfer.files;

          if (allFiles.length > 0) {
              $uploadedFilesContainer.show();
          }

          $fileListContainer.empty();
          allFiles.forEach(function (file) {
              var fileName = file.name;
              var displayName = fileName.length > 15 ? fileName.substring(0, 12) + '...' : fileName;

              var $fileCol = $(`
                  <div class="col-3 mb-2 file-item" data-filename="${fileName}" data-toggle="tooltip" title="${fileName}">
                      <span class="d-inline-block text-truncate">${displayName}</span>
                      <button class="btn btn-sm btn-outline-danger float-right delete-file-btn">
                          <i class="bi bi-trash"></i>
                      </button>
                  </div>
              `);

              $fileCol.find('.delete-file-btn').on('click', function () {
                  $fileCol.tooltip('dispose'); 
                  $fileCol.remove();
                  allFiles = allFiles.filter(f => f.name !== fileName); 

                  var updatedDataTransfer = new DataTransfer();
                  allFiles.forEach(f => updatedDataTransfer.items.add(f));
                  document.getElementById('docUploadUnique').files = updatedDataTransfer.files;

                  if ($fileListContainer.children().length === 0) {
                      $uploadedFilesContainer.hide();
                      $('#docUploadUnique').val('');
                  }
              });

              $fileListContainer.append($fileCol);
          });

          $('[data-toggle="tooltip"]').tooltip();
      });
    });

  

    function adjustMessageActions(messageElement) {
      // Ensure the element is visible before measuring
      const messageActions = messageElement.find('.message-actions');
      messageActions.css('display', 'block'); // Temporarily make actions visible if hidden
  
      const messageText = messageElement.find('.text');
      const messageTextHeight = messageText.outerHeight(true); // Include margins in height calculation
      const messageTextWidth = messageText.outerWidth(true);  // Include margins in width calculation
  
      if (messageTextHeight > 0 && messageTextWidth > 0) {
          // Dynamically position actions
          let adjustedTop = messageTextHeight;
          if (messageTextHeight > 100) {
              adjustedTop += 5;
          }
  
          // Apply the -69px left offset
          // const adjustedLeft = messageTextWidth - messageActions.outerWidth() - 69; // Adjusted left by -69px
          const adjustedLeft = -100; // Adjusted left by -69px
  
          messageActions.css({
              'margin-top': `${adjustedTop}px`,
              'margin-left': `${adjustedLeft}px`,  // Apply the calculated margin-left
          });
      } else {
          console.warn("Failed to measure element dimensions. Ensure it's visible and styled properly.");
      }
  
      // Do not hide it right after the adjustment unless explicitly needed for another reason
      // messageActions.hide();  // Uncomment this only if you need to hide it again after positioning
  }
  
  
  function callBotAPI(userMessage) {
    const userMessageInput = $('#userMessage'); // Reference to the input field

    // Disable the input field
    userMessageInput.prop('disabled', true);

    // Add a three-dots loader
    const typingIndicator = $(`
      <div class="message bot typing-indicator">
        <div class="text analyzing-loader">
          <span>.</span><span>.</span><span>.</span>
        </div>
      </div>`);
    $('#chatBox').append(typingIndicator);
    $('#chatBox').animate({ scrollTop: $('#chatBox').prop("scrollHeight") }, 500);

    $.ajax({
        url: '/query',
        method: 'POST',
        data: JSON.stringify({ query: userMessage }),
        contentType: 'application/json',
        success: function (response) {
            // Remove the typing indicator
            typingIndicator.remove();

            const botMessage = response || "Sorry, I couldn't find an answer to that.";
            typingEffect(botMessage);

            // Re-enable the input field after the typing effect is complete
            setTimeout(() => {
                userMessageInput.prop('disabled', false);
                userMessageInput.focus(); // Optionally set focus back to the input field
            }, botMessage.length * 50); // Adjust delay based on typing speed
        },
        error: function () {
            // Remove the typing indicator
            typingIndicator.remove();

            typingEffect("Sorry, something went wrong. Please try again later.");

            // Re-enable the input field after typing effect is complete
            setTimeout(() => {
                userMessageInput.prop('disabled', false);
                userMessageInput.focus(); // Optionally set focus back to the input field
            }, 2000); // Set a fixed delay for error messages
        }
    });
}

  
  

  let uploadedFilesArray = [];
  

$(document).on('click', '#uploadBtn', function () {
    
    $('#pdfInput').click();
  });

  $(document).on('change','#pdfInput',function(event) {
    let files = Array.from(event.target.files);
    let duplicateFound = false;

    files.forEach((file) => {
      let fileName = file.name;

      if (uploadedFilesArray.some(uploadedFile => uploadedFile.name === fileName)) {
        showError(`The file "${fileName}" is already uploaded.`);
        duplicateFound = true;
      } else {
        uploadedFilesArray.push(file);
        $('#errorMessage').hide();
      }
    });

    if (!duplicateFound) {
      displayUploadedFiles();
    }

    $('#pdfInput').val('');
  });

  function displayUploadedFiles() {
    let uploadedFilesList = $('#uploadedFiles');
    uploadedFilesList.empty();
    if(uploadedFilesArray.length > 0 ){
      $('#pdfCount').text(uploadedFilesArray.length);
    }else{
      $('#pdfCount').text('');
    }

    uploadedFilesArray.forEach((file, index) => {
      let fileName = file.name;
      let shortFileName = fileName.length > 20 ? fileName.substring(0, 20) + '...' : fileName;

      uploadedFilesList.append(
        `<div class="file-item d-flex justify-content-between align-items-center mb-2 p-2" style="background-color: #f8f9fa; border-radius: 5px;">
          <span data-toggle="tooltip" title="${fileName}" class="file-name" style="color: black;">${shortFileName}</span>
          <span class="remove-file text-danger" data-index="${index}" style="cursor:pointer;">&times;</span>
        </div>`
      );
    });

    $('[data-toggle="tooltip"]').tooltip();
    toggleProcessButton();
  }

  $('#uploadedFiles').on('click', '.remove-file', function() {
    let fileIndex = $(this).data('index');
    uploadedFilesArray.splice(fileIndex, 1);
    displayUploadedFiles();
  });

  function showError(message) {
    $('#errorMessage').text(message).show();
  }

  function toggleProcessButton() {
    if (uploadedFilesArray.length > 0) {
      $('#processBtn').removeClass('d-none');
    } else {
      $('#processBtn').addClass('d-none');
    }
  }

  function displayUploadedFiles() {
    let uploadedFilesList = $('#uploadedFiles');
    uploadedFilesList.empty();

    if(uploadedFilesArray.length > 0 ){
      $('#pdfCount').text(uploadedFilesArray.length);
    }else{
      $('#pdfCount').text('');
    }

    uploadedFilesArray.forEach((file, index) => {
      let fileName = file.name;
      let shortFileName = fileName.length > 20 ? fileName.substring(0, 20) + '...' : fileName;

      uploadedFilesList.append(
        `<div class="file-item d-flex justify-content-between align-items-center mb-2 p-2" style="background-color: #f8f9fa; border-radius: 5px;" id="file-item-${index}">
          <span class="file-status" id="file-status-${index}" style="display:none;">
            <i class="fas fa-spinner fa-spin text-secondary"></i> <!-- Placeholder spinner -->
          </span>
          <span data-toggle="tooltip" title="${fileName}" class="file-name" style="color: black;">${shortFileName}</span>
          <span class="remove-file text-danger" data-index="${index}" style="cursor:pointer;">&times;</span>
        </div>`
      );
    });

    $('[data-toggle="tooltip"]').tooltip();
    toggleProcessButton();
  }


  $('#processBtn').click(function() {
    if (uploadedFilesArray.length > 0) {
      $('#processBtn').prop('disabled', true);
      $('#processBtn').html('Processing...');
      $('.remove-file').addClass('d-none');

      uploadedFilesArray.forEach((file, index) => {
        let formData = new FormData();
        formData.append('pdf', file);
        $(`#file-status-${index}`).show();

        $.ajax({
          url: '/upload_pdf',
          method: 'POST',
          data: formData,
          processData: false,
          contentType: false,
          success: function(response) {
            $(`#file-status-${index}`).html('<i class="fas fa-check text-success"></i>');
            $('#processBtn').html('Processed');
            $('#pdfCount').text('');
            displayFinalNotification();
            console.log(`File ${file.name} processed successfully`);
          },
          error: function(xhr, status, error) {
            $(`#file-status-${index}`).html('<i class="fas fa-exclamation text-danger"></i>');  
            console.log(`Error processing file ${file.name}:, error`);
          },
          complete: function() {
            if (uploadedFilesArray.every((file, i) => $(`#file-status-${i}`).find('.fa-check-circle').length)) {
              $('#processBtn').html('Process').prop('disabled', false);
              $('#pdfCount').text('0');
              uploadedFilesArray = [];
              setTimeout(displayUploadedFiles, 2000);
            }
          }
        });
      });
    } else {
      showError('Please upload at least one PDF.');
    }
  });



  function showSuccess(message) {
      $('#errorMessage').hide();
      $('#processBtn').html('<i class="fas fa-check-circle"></i> Done').prop('disabled', false);
      setTimeout(function () {
        $('#processBtn').html('Process');
        $('#pdfCount').text('0');
        uploadedFilesArray = [];
        displayUploadedFiles();
      }, 2000);
  }
  
  function displayFinalNotification() {
    // console.log('Displaying final notification...');  // Debugging line
    const finalMessage = $(`
      <div class="alert alert-success mt-3 final-notification">
        <strong>All files have been processed!</strong> You can now chat with your documents.
      </div>
    `);

    $('#successMessage').append(finalMessage);

    finalMessage.fadeIn('slow').delay(4000).fadeOut('slow', function() {
        $(this).remove();  // Remove the message after fading out

        // Check if the button text is "Show Uploaded Files" and simulate click if true
        if ($('#togglePdfNamesBtn').text() == "Show Uploaded Files") {
            $('#togglePdfNamesBtn').click();  // Simulate the click event
        }
    });

    $('#processBtn').prop('disabled', false).html('Process');
    $('#pdfCount').text('0');
    uploadedFilesArray = [];
    setTimeout(displayUploadedFiles, 2000);
}
});



$(document).ready(function () {
 
// File upload handler
$('#pdfInput').change(function (event) {
let files = Array.from(event.target.files);
files.forEach((file) => {
  let formData = new FormData();
  formData.append('pdf', file);
});
});
$('#togglePdfNamesBtn').click(function() {
let isShowing = $(this).text() === "Hide Uploaded Files";

if (isShowing) {
  // Hide the list and change button text
  $('#pdfNamesContainer').fadeOut(300);
  $(this).text("Show Uploaded Files");
} else {
  // Show the list with animation and fetch PDF names
  $.ajax({
    url: '/list_pdfs',
    method: 'GET',
    success: function(response) {
      let pdfNames = response.pdfNames;
      let pdfListHtml = '<div class="pdf-list">';
      pdfNames.forEach(function(filePath) {
        let shortFileName = filePath.split('/').pop(); 
        let displayName = shortFileName.length > 20 ? shortFileName.substring(0, 20) + '...' : shortFileName;
      
      pdfListHtml += 
        `<div class="pdf-name-item" data-toggle="tooltip" title="${filePath}">
          ${displayName}
        </div>`;

      });
      pdfListHtml += '</div>';
      $('#pdfNamesContainer').html(pdfListHtml).fadeIn(300);
      $('#togglePdfNamesBtn').text("Hide Uploaded Files");
      $('[data-toggle="tooltip"]').tooltip();
    },
    error: function() {
      $('#pdfNamesContainer').html('<p class="text-danger">Error fetching PDF names.</p>').fadeIn(300);
    }
  });
}
});

});