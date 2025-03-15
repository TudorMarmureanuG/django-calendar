# Django Calendar Application

This Django application allows users to generate a timetable/calendar for each registered account, enabling them to add various events and manage group event (works only for superusers).

## Features

- User registration and authentication
- Event creation and management
- Calendar view displaying events
* For Superusers only:
   - Create groups and manage the events for the members of the groups

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   ```

2. Navigate to the project directory:
   ```
   cd django-calendar
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Run migrations:
   ```
   python manage.py migrate
   ```

5. Start the development server:
   ```
   python manage.py runserver
   ```

## Usage

- Visit `http://127.0.0.1:8000/` to access the application.
- Register a new account or log in to an existing account to start managing your events.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.