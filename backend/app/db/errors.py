"""Only connectivity/pool failures represent temporary dependency unavailability."""

from sqlalchemy.exc import DisconnectionError, InterfaceError, OperationalError, TimeoutError

DATABASE_AVAILABILITY_ERRORS = (DisconnectionError, InterfaceError, OperationalError, TimeoutError)
