// static/js/admin/code_editor.js
document.addEventListener('DOMContentLoaded', function() {
    // Find all monaco editor containers
    const editorContainers = document.querySelectorAll('.monaco-editor-container');

    if (editorContainers.length === 0) {
        return;
    }

    require.config({ paths: {
        vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs'
    }});

    require(['vs/editor/editor.main'], function() {
        editorContainers.forEach(function(container) {
            // Extract the field name from the container id (format: monaco-editor-{fieldname})
            const fieldName = container.id.replace('monaco-editor-', '');
            const textarea = document.getElementById('id_' + fieldName);

            if (!textarea) {
                console.warn('CodeEditorPanel: Could not find textarea for field:', fieldName);
                return;
            }

            // Determine language based on field name
            let language = 'html';
            if (fieldName === 'css') {
                language = 'css';
            } else if (fieldName === 'javascript') {
                language = 'javascript';
            }

            const editor = monaco.editor.create(container, {
                value: textarea.value || '',
                language: language,
                theme: 'vs-dark',
                automaticLayout: true,
                minimap: { enabled: true },
                scrollBeyondLastLine: false,
                fontSize: 14,
            });

            // Sync editor content back to textarea on change
            editor.onDidChangeModelContent(function() {
                textarea.value = editor.getValue();
            });
        });
    });
});
