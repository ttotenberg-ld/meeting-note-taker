// DOM elements
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const elapsedTime = document.getElementById("elapsed-time");
const meetingTitle = document.getElementById("meeting-title");
const meetingAttendees = document.getElementById("meeting-attendees");
const meetingTime = document.getElementById("meeting-time");
const recordBtn = document.getElementById("record-btn");
const recordBtnText = document.getElementById("record-btn-text");
const processingBanner = document.getElementById("processing-banner");
const processingStep = document.getElementById("processing-step");
const errorBanner = document.getElementById("error-banner");
const errorText = document.getElementById("error-text");
const notesList = document.getElementById("notes-list");
const changeMeetingBtn = document.getElementById("change-meeting-btn");
const selectedMeetingDisplay = document.getElementById("selected-meeting-display");
const meetingPicker = document.getElementById("meeting-picker");
const meetingOptions = document.getElementById("meeting-options");
const customTitleInput = document.getElementById("custom-title-input");
const useCustomBtn = document.getElementById("use-custom-btn");

// State
let isRecording = false;
let isProcessing = false;
let timerInterval = null;
let statusPollInterval = null;
let recordingStartTime = null;
let selectedMeeting = null; // the meeting (or custom obj) that will be recorded
let pickerOpen = false;

// Config (loaded from backend)
let obsidianVaultName = "";
let obsidianNotesSubpath = "";

// --- Initialization ---

async function init() {
  try {
    await api.health();

    // Load config from backend
    const cfg = await api.config();
    obsidianVaultName = cfg.obsidian_vault_name || "";
    obsidianNotesSubpath = cfg.obsidian_notes_subpath || "";

    setStatus("idle", "Ready to record");
    recordBtn.disabled = false;
    fetchAndAutoSelect();
    fetchNotesList();

    // Poll meeting info every 60s (only auto-update if nothing is selected)
    setInterval(() => {
      if (!selectedMeeting && !pickerOpen && !isRecording) {
        fetchAndAutoSelect();
      }
    }, 60000);
    // Poll notes list every 30s
    setInterval(fetchNotesList, 30000);
  } catch {
    setStatus("error", "Backend not reachable");
    recordBtn.disabled = true;
    setTimeout(init, 3000);
  }
}

// --- Meeting Selection ---

async function fetchAndAutoSelect() {
  try {
    const data = await api.currentMeeting();
    if (data.meeting) {
      selectMeeting(data.meeting);
    } else {
      meetingTitle.textContent = "No multi-person meetings found";
      meetingAttendees.textContent = "";
      meetingTime.textContent = "";
      changeMeetingBtn.style.display = "inline-block";
      changeMeetingBtn.textContent = "Pick";
    }
  } catch {
    meetingTitle.textContent = "Calendar unavailable";
    meetingAttendees.textContent = "";
    meetingTime.textContent = "";
    changeMeetingBtn.style.display = "inline-block";
    changeMeetingBtn.textContent = "Pick";
  }
}

function selectMeeting(meeting) {
  selectedMeeting = meeting;
  meetingTitle.textContent = meeting.title;

  const names = meeting.attendees.map((a) => a.name).join(", ");
  meetingAttendees.textContent = names ? `with ${names}` : "";

  const start = formatTime(meeting.start);
  const end = formatTime(meeting.end);
  meetingTime.textContent = start && end ? `${start} - ${end}` : "";

  changeMeetingBtn.style.display = "inline-block";
  changeMeetingBtn.textContent = "Change";
  closePicker();
}

function selectCustomTitle(title) {
  selectedMeeting = {
    title: title || "Untitled Recording",
    start: "",
    end: "",
    attendees: [],
    description: "",
    meeting_link: "",
    _custom: true,
  };

  meetingTitle.textContent = selectedMeeting.title;
  meetingAttendees.textContent = "No calendar meeting";
  meetingTime.textContent = "";

  changeMeetingBtn.style.display = "inline-block";
  changeMeetingBtn.textContent = "Change";
  closePicker();
}

// --- Picker UI ---

changeMeetingBtn.addEventListener("click", () => {
  if (pickerOpen) {
    closePicker();
  } else {
    openPicker();
  }
});

useCustomBtn.addEventListener("click", () => {
  selectCustomTitle(customTitleInput.value.trim());
});

customTitleInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    selectCustomTitle(customTitleInput.value.trim());
  }
});

async function openPicker() {
  pickerOpen = true;
  selectedMeetingDisplay.style.display = "none";
  meetingPicker.style.display = "block";
  changeMeetingBtn.textContent = "Cancel";
  customTitleInput.value = "";

  // Fetch upcoming meetings
  meetingOptions.innerHTML = '<li class="meeting-option-item loading">Loading...</li>';
  try {
    const data = await api.upcomingMeetings();
    if (data.meetings && data.meetings.length > 0) {
      meetingOptions.innerHTML = data.meetings
        .map((m) => {
          const names = m.attendees.map((a) => a.name).join(", ");
          const time = formatTime(m.start);
          const attendeeCount = m.attendees.length;
          const badge =
            attendeeCount >= 2
              ? `<span class="attendee-badge">${attendeeCount}</span>`
              : `<span class="attendee-badge solo">1</span>`;
          return `
            <li class="meeting-option-item" data-meeting-id="${escapeHtml(m.id)}">
              <div class="meeting-option-top">
                ${badge}
                <span class="meeting-option-title">${escapeHtml(m.title)}</span>
              </div>
              <div class="meeting-option-meta">${time ? time + " - " : ""}${escapeHtml(names) || "Just you"}</div>
            </li>
          `;
        })
        .join("");

      // Add click handlers
      meetingOptions.querySelectorAll(".meeting-option-item").forEach((li, idx) => {
        li.addEventListener("click", () => {
          selectMeeting(data.meetings[idx]);
        });
      });
    } else {
      meetingOptions.innerHTML =
        '<li class="meeting-option-item loading">No upcoming meetings</li>';
    }
  } catch {
    meetingOptions.innerHTML =
      '<li class="meeting-option-item loading">Failed to load meetings</li>';
  }
}

function closePicker() {
  pickerOpen = false;
  selectedMeetingDisplay.style.display = "block";
  meetingPicker.style.display = "none";
  changeMeetingBtn.textContent = selectedMeeting ? "Change" : "Pick";
}

// --- Recording ---

recordBtn.addEventListener("click", async () => {
  if (isProcessing) return;

  if (!isRecording) {
    await startRecording();
  } else {
    await stopRecording();
  }
});

async function startRecording() {
  try {
    recordBtn.disabled = true;

    // Build request body based on selection
    const body = {};
    if (selectedMeeting && selectedMeeting._custom) {
      body.custom_title = selectedMeeting.title;
    } else if (selectedMeeting) {
      body.meeting = selectedMeeting;
    }

    await api.startRecording(body);
    isRecording = true;
    setStatus("recording", "Recording...");
    recordBtn.classList.remove("start");
    recordBtn.classList.add("stop");
    recordBtnText.textContent = "Stop Recording";
    recordBtn.disabled = false;
    changeMeetingBtn.style.display = "none";
    hideError();

    // Start timer
    recordingStartTime = Date.now();
    elapsedTime.style.display = "inline";
    timerInterval = setInterval(updateTimer, 1000);
  } catch (err) {
    showError(`Failed to start recording: ${err.message}`);
    recordBtn.disabled = false;
  }
}

async function stopRecording() {
  try {
    recordBtn.disabled = true;
    isRecording = false;
    clearInterval(timerInterval);
    elapsedTime.style.display = "none";

    await api.stopRecording();
    isProcessing = true;
    setStatus("processing", "Processing...");
    recordBtn.classList.remove("stop");
    recordBtn.classList.add("start");
    recordBtnText.textContent = "Start Recording";
    showProcessing("Transcribing audio...");

    // Poll for processing status
    statusPollInterval = setInterval(pollProcessingStatus, 2000);
  } catch (err) {
    showError(`Failed to stop recording: ${err.message}`);
    recordBtn.disabled = false;
  }
}

async function pollProcessingStatus() {
  try {
    const data = await api.recordingStatus();

    if (data.error) {
      clearInterval(statusPollInterval);
      isProcessing = false;
      hideProcessing();
      showError(data.error);
      setStatus("idle", "Ready to record");
      recordBtn.disabled = false;
      changeMeetingBtn.style.display = "inline-block";
      return;
    }

    if (data.step) {
      updateProcessingStep(data.step);
    }

    if (data.state === "idle" && data.step === "Done!") {
      clearInterval(statusPollInterval);
      isProcessing = false;
      hideProcessing();
      setStatus("idle", "Notes saved!");
      recordBtn.disabled = false;
      changeMeetingBtn.style.display = "inline-block";
      fetchNotesList();

      // Reset for next recording
      selectedMeeting = null;
      setTimeout(() => {
        if (!isRecording && !isProcessing) {
          setStatus("idle", "Ready to record");
          fetchAndAutoSelect();
        }
      }, 3000);
    }
  } catch {
    // Ignore transient errors during polling
  }
}

// --- Notes List ---

function openInObsidian(filename) {
  if (!obsidianVaultName) return;
  // Strip .md extension — Obsidian URIs use the file path without it
  const fileWithoutExt = filename.replace(/\.md$/, "");
  const filePath = obsidianNotesSubpath
    ? `${obsidianNotesSubpath}/${fileWithoutExt}`
    : fileWithoutExt;
  const url = `obsidian://open?vault=${encodeURIComponent(obsidianVaultName)}&file=${encodeURIComponent(filePath)}`;
  window.electronAPI.openExternal(url);
}

async function fetchNotesList() {
  try {
    const data = await api.listNotes();
    if (data.notes && data.notes.length > 0) {
      notesList.innerHTML = data.notes
        .map(
          (note) => `
        <li class="note-item clickable" data-filename="${escapeHtml(note.filename)}">
          <span class="note-icon">&#128221;</span>
          <div class="note-info">
            <div class="note-title">${escapeHtml(note.title)}</div>
            <div class="note-date">${escapeHtml(note.date)}</div>
          </div>
          <span class="note-open-icon">&#8599;</span>
        </li>
      `
        )
        .join("");

      // Add click handlers
      notesList.querySelectorAll(".note-item.clickable").forEach((li) => {
        li.addEventListener("click", () => {
          openInObsidian(li.dataset.filename);
        });
      });
    } else {
      notesList.innerHTML = '<li class="empty-state">No recordings yet</li>';
    }
  } catch {
    // Silently fail
  }
}

// --- UI Helpers ---

function setStatus(state, text) {
  statusDot.className = `status-dot ${state}`;
  statusText.textContent = text;
}

function updateTimer() {
  if (!recordingStartTime) return;
  const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
  const h = String(Math.floor(elapsed / 3600)).padStart(2, "0");
  const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
  const s = String(elapsed % 60).padStart(2, "0");
  elapsedTime.textContent = `${h}:${m}:${s}`;
}

function showProcessing(step) {
  processingBanner.classList.add("visible");
  processingStep.textContent = step;
}

function updateProcessingStep(step) {
  processingStep.textContent = step;
}

function hideProcessing() {
  processingBanner.classList.remove("visible");
}

function showError(msg) {
  errorBanner.classList.add("visible");
  errorText.textContent = msg;
}

function hideError() {
  errorBanner.classList.remove("visible");
}

function formatTime(isoString) {
  if (!isoString) return "";
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return isoString;
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// --- Start ---
init();
