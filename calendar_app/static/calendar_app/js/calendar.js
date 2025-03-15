document.addEventListener('DOMContentLoaded', function() {
    const eventForm = document.getElementById('event-form');
    const eventList = document.getElementById('event-list');

    // Function to add an event to the list
    function addEvent(event) {
        event.preventDefault();
        const title = event.target.title.value;
        const date = event.target.date.value;

        if (title && date) {
            const listItem = document.createElement('li');
            listItem.textContent = `${title} - ${date}`;
            eventList.appendChild(listItem);
            eventForm.reset();
        }
    }

    // Attach event listener to the form
    if (eventForm) {
        eventForm.addEventListener('submit', addEvent);
    }
});