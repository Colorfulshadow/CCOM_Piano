/**
 * CCOM Piano Reservation System
 * Main JavaScript file
 */

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Initialize countdown timer if present
    initCountdown();

    // Initialize time input formatting
    initTimeInputs();

    // Setup confirmation dialogs
    setupConfirmationDialogs();
});

/**
 * Initialize countdown timer
 */
function initCountdown() {
    const countdownElement = document.getElementById('countdown-timer');
    if (!countdownElement) return;

    const targetTime = countdownElement.getAttribute('data-target-time');
    if (!targetTime) return;

    // Update the countdown every second
    updateCountdown(countdownElement, targetTime);
    setInterval(() => updateCountdown(countdownElement, targetTime), 1000);
}

/**
 * Update countdown timer display
 */
function updateCountdown(element, targetTimeStr) {
    const now = new Date();
    const targetTime = new Date(targetTimeStr);

    // Calculate the time difference in seconds
    let diff = Math.floor((targetTime - now) / 1000);

    if (diff <= 0) {
        element.textContent = "Now!";
        return;
    }

    // Calculate hours, minutes, seconds
    const hours = Math.floor(diff / 3600);
    diff -= hours * 3600;
    const minutes = Math.floor(diff / 60);
    diff -= minutes * 60;
    const seconds = diff;

    // Format the time
    element.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

/**
 * Initialize time input formatting
 */
function initTimeInputs() {
    const timeInputs = document.querySelectorAll('input[type="time"]');
    timeInputs.forEach(input => {
        input.addEventListener('change', function() {
            // Ensure the value is formatted correctly for the backend (HHMM)
            const hiddenInput = document.querySelector(`input[name="${this.dataset.target}"]`);
            if (hiddenInput && this.value) {
                hiddenInput.value = this.value.replace(':', '');
            }
        });
    });
}

/**
 * Setup confirmation dialogs for dangerous actions
 */
function setupConfirmationDialogs() {
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm(this.dataset.confirm)) {
                e.preventDefault();
                return false;
            }
        });
    });
}

/**
 * Format time string from HHMM to HH:MM
 */
function formatTime(timeStr) {
    if (!timeStr || timeStr.length !== 4) return timeStr;
    return `${timeStr.substr(0, 2)}:${timeStr.substr(2, 2)}`;
}

/**
 * Check room availability from the server
 */
function checkRoomAvailability(roomId, date) {
    if (!roomId || !date) return;

    const availabilityContainer = document.getElementById('availability-container');
    const loadingSpinner = document.getElementById('loading-spinner');

    if (!availabilityContainer || !loadingSpinner) return;

    // Show loading spinner
    availabilityContainer.classList.add('d-none');
    loadingSpinner.classList.remove('d-none');

    // Make the API request
    fetch(`/reservation/check-availability?room_id=${roomId}&date=${date}`)
        .then(response => response.json())
        .then(data => {
            // Hide loading spinner
            loadingSpinner.classList.add('d-none');
            availabilityContainer.classList.remove('d-none');

            if (data.error) {
                showAlert('danger', `Error: ${data.error}`);
                return;
            }

            // Process and display the availability data
            displayAvailability(data);
        })
        .catch(error => {
            // Hide loading spinner
            loadingSpinner.classList.add('d-none');

            // Show error message
            showAlert('danger', `Error: ${error.message}`);
        });
}

/**
 * Display room availability data
 */
function displayAvailability(data) {
    const container = document.getElementById('availability-container');
    if (!container) return;

    // Clear previous content
    container.innerHTML = '';

    if (!data.remainingTimeList || data.remainingTimeList.length === 0) {
        container.innerHTML = '<div class="alert alert-info">No availability information found for this room on the selected date.</div>';
        return;
    }

    // Create a table to display the availability
    const table = document.createElement('table');
    table.className = 'table table-striped table-bordered';

    // Table header
    const thead = document.createElement('thead');
    const headerRow = document.createElement('tr');
    headerRow.innerHTML = `
        <th>Start Time</th>
        <th>End Time</th>
        <th>Duration</th>
        <th>Action</th>
    `;
    thead.appendChild(headerRow);
    table.appendChild(thead);

    // Table body
    const tbody = document.createElement('tbody');

    data.remainingTimeList.forEach(slot => {
        const row = document.createElement('tr');

        // Convert timestamps to time strings
        const startTime = new Date(slot.startTime);
        const endTime = new Date(slot.endTime);

        // Format times as HH:MM
        const startHour = startTime.getHours().toString().padStart(2, '0');
        const startMinute = startTime.getMinutes().toString().padStart(2, '0');
        const endHour = endTime.getHours().toString().padStart(2, '0');
        const endMinute = endTime.getMinutes().toString().padStart(2, '0');

        const startTimeStr = `${startHour}:${startMinute}`;
        const endTimeStr = `${endHour}:${endMinute}`;

        // Calculate duration in hours and minutes
        const durationMinutes = (endTime - startTime) / (1000 * 60);
        const hours = Math.floor(durationMinutes / 60);
        const minutes = durationMinutes % 60;
        const durationStr = `${hours}h ${minutes}m`;

        // Populate the row
        row.innerHTML = `
            <td>${startTimeStr}</td>
            <td>${endTimeStr}</td>
            <td>${durationStr}</td>
            <td>
                <button class="btn btn-sm btn-primary select-time-btn" 
                        data-start-time="${startHour}${startMinute}" 
                        data-end-time="${endHour}${endMinute}">
                    Select
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });

    table.appendChild(tbody);
    container.appendChild(table);

    // Add click event listeners for select buttons
    const selectButtons = container.querySelectorAll('.select-time-btn');
    selectButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Populate the form inputs with the selected time slot
            const startTimeInput = document.querySelector('input[name="start_time"]');
            const endTimeInput = document.querySelector('input[name="end_time"]');
            const startTimeDisplay = document.querySelector('input[name="start_time_display"]');
            const endTimeDisplay = document.querySelector('input[name="end_time_display"]');

            if (startTimeInput && endTimeInput) {
                startTimeInput.value = this.dataset.startTime;
                endTimeInput.value = this.dataset.endTime;
            }

            if (startTimeDisplay && endTimeDisplay) {
                startTimeDisplay.value = formatTime(this.dataset.startTime);
                endTimeDisplay.value = formatTime(this.dataset.endTime);
            }

            // Scroll to the form
            document.getElementById('reservation-form').scrollIntoView({ behavior: 'smooth' });
        });
    });
}

/**
 * Show an alert message
 */
function showAlert(type, message) {
    const alertContainer = document.getElementById('alert-container');
    if (!alertContainer) return;

    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    alertContainer.appendChild(alert);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
    }, 5000);
}

/**
 * Check server time (admin function)
 */
function checkServerTime() {
    const serverTimeElement = document.getElementById('server-time');
    const localTimeElement = document.getElementById('local-time');
    const latencyElement = document.getElementById('latency');
    const nextReservationElement = document.getElementById('next-reservation-time');

    if (!serverTimeElement) return;

    fetch('/admin/system/server-time')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showAlert('danger', `Error: ${data.error}`);
                return;
            }

            serverTimeElement.textContent = data.server_time;
            localTimeElement.textContent = data.local_time;
            latencyElement.textContent = `${data.latency_ms.toFixed(2)} ms`;
            nextReservationElement.textContent = data.next_reservation_time;
        })
        .catch(error => {
            showAlert('danger', `Error: ${error.message}`);
        });
}