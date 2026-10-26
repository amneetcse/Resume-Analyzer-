const fileInput = document.querySelector('#resume-file');
const dropzone = document.querySelector('#dropzone');
const fileLabel = document.querySelector('#file-label');
const fileMeta = document.querySelector('#file-meta');

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
}

function showFile(file) {
  if (!file || !fileLabel || !fileMeta) return;
  fileLabel.innerHTML = `<b>${escapeHtml(file.name)}</b><span>Selected and ready to analyze</span>`;
  fileMeta.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
}

if (fileInput && dropzone) {
  fileInput.addEventListener('change', () => showFile(fileInput.files[0]));
  ['dragenter', 'dragover'].forEach(type => dropzone.addEventListener(type, event => {
    event.preventDefault();
    dropzone.classList.add('dragging');
  }));
  ['dragleave', 'drop'].forEach(type => dropzone.addEventListener(type, event => {
    event.preventDefault();
    dropzone.classList.remove('dragging');
  }));
  dropzone.addEventListener('drop', event => {
    const file = event.dataTransfer.files[0];
    if (!file) return;
    const transfer = new DataTransfer();
    transfer.items.add(file);
    fileInput.files = transfer.files;
    showFile(file);
  });
}

const themeButton = document.querySelector('.theme-toggle');
if (themeButton) {
  const body = document.body;
  if (localStorage.getItem('resumeai-theme') === 'dark') body.classList.add('dark-mode');
  themeButton.addEventListener('click', () => {
    body.classList.toggle('dark-mode');
    localStorage.setItem('resumeai-theme', body.classList.contains('dark-mode') ? 'dark' : 'light');
  });
}
