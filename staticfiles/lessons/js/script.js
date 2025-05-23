document.addEventListener('DOMContentLoaded', function() {
    // File input preview for upload form
    const fileInput = document.getElementById('id_file');
    const thumbnailInput = document.getElementById('id_thumbnail');
    
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const fileName = e.target.files[0]?.name || 'No file selected';
            document.querySelector('.file-name').textContent = fileName;
        });
    }
    
    if (thumbnailInput) {
        thumbnailInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    document.getElementById('thumbnail-preview').src = event.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    }

    // Markdown editor for content field
    const contentField = document.getElementById('id_content');
    if (contentField) {
        const toolbar = document.createElement('div');
        toolbar.className = 'markdown-toolbar mb-2';
        toolbar.innerHTML = `
            <button type="button" class="btn btn-sm btn-outline-secondary" data-md-command="bold"><i class="fas fa-bold"></i></button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-md-command="italic"><i class="fas fa-italic"></i></button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-md-command="heading"><i class="fas fa-heading"></i></button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-md-command="link"><i class="fas fa-link"></i></button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-md-command="code"><i class="fas fa-code"></i></button>
            <button type="button" class="btn btn-sm btn-outline-secondary" data-md-command="list"><i class="fas fa-list-ul"></i></button>
        `;
        contentField.parentNode.insertBefore(toolbar, contentField);

        // Add toolbar functionality
        toolbar.querySelectorAll('[data-md-command]').forEach(button => {
            button.addEventListener('click', function() {
                const command = this.getAttribute('data-md-command');
                const start = contentField.selectionStart;
                const end = contentField.selectionEnd;
                const selectedText = contentField.value.substring(start, end);
                let newText = '';

                switch(command) {
                    case 'bold':
                        newText = `**${selectedText}**`;
                        break;
                    case 'italic':
                        newText = `*${selectedText}*`;
                        break;
                    case 'heading':
                        newText = `## ${selectedText}`;
                        break;
                    case 'link':
                        newText = `[${selectedText}](url)`;
                        break;
                    case 'code':
                        newText = selectedText.includes('\n') 
                            ? `\`\`\`\n${selectedText}\n\`\`\`` 
                            : `\`${selectedText}\``;
                        break;
                    case 'list':
                        newText = selectedText.split('\n').map(line => `- ${line}`).join('\n');
                        break;
                }

                contentField.value = contentField.value.substring(0, start) + newText + contentField.value.substring(end);
                contentField.focus();
                contentField.selectionStart = start + newText.length;
                contentField.selectionEnd = start + newText.length;
            });
        });
    }

    // PDF viewer adjustments
    const pdfViewer = document.querySelector('.file-preview iframe');
    if (pdfViewer) {
        pdfViewer.style.height = `${window.innerHeight * 0.6}px`;
    }
});