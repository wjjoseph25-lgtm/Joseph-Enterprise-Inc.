const input = document.querySelector("#videoInput");
const card = document.querySelector("#uploadCard");
const idle = document.querySelector("#uploadIdle");
const processing = document.querySelector("#uploadProcessing");
const progressBar = document.querySelector("#progressBar");
const progressText = document.querySelector("#progressText");
const statusText = document.querySelector("#statusText");
const toast = document.querySelector("#toast");
let timer;

document.querySelector("#chooseButton").addEventListener("click", () => input.click());
input.addEventListener("change", () => input.files[0] && processFile(input.files[0]));
["dragenter", "dragover"].forEach(name => card.addEventListener(name, event => { event.preventDefault(); card.classList.add("dragover"); }));
["dragleave", "drop"].forEach(name => card.addEventListener(name, event => { event.preventDefault(); card.classList.remove("dragover"); }));
card.addEventListener("drop", event => event.dataTransfer.files[0] && processFile(event.dataTransfer.files[0]));
document.querySelector("#cancelButton").addEventListener("click", resetUpload);

function processFile(file) {
  if (!file.type.startsWith("video/")) return showToast("Please choose a video file.");
  document.querySelector("#fileName").textContent = file.name;
  document.querySelector("#fileSize").textContent = `${(file.size / 1048576).toFixed(1)} MB · Secure upload`;
  idle.hidden = true;
  processing.hidden = false;
  let progress = 0;
  clearInterval(timer);
  timer = setInterval(() => {
    progress = Math.min(progress + Math.ceil(Math.random() * 8), 100);
    progressBar.style.width = `${progress}%`;
    progressText.textContent = `${progress}%`;
    statusText.textContent = progress < 55 ? "Uploading…" : progress < 90 ? "Preparing audio…" : "Finding your best moments…";
    if (progress === 100) { clearInterval(timer); showToast("Video ready — your clips are being created."); }
  }, 220);
}

function resetUpload() {
  clearInterval(timer); input.value = ""; progressBar.style.width = "0"; progressText.textContent = "0%";
  processing.hidden = true; idle.hidden = false;
}

function showToast(message) {
  toast.textContent = message; toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3200);
}
