"""
@Author: Tianyi Zhang
@Date: 2025/4/26
@Description: 
"""
class ApiError(Exception):
    """Base exception for API errors"""
    def __init__(self, message="API error occurred"):
        self.message = message
        super().__init__(self.message)


class LoginError(ApiError):
    """Exception raised when login fails or session is invalid"""
    def __init__(self, message="Login failed or session expired"):
        self.message = message
        super().__init__(self.message)


class AlreadyChosen(ApiError):
    """Exception raised when trying to reserve an already reserved room"""
    def __init__(self, message="Already reserved this room for this time slot"):
        self.message = message
        super().__init__(self.message)


class FailedToChoose(ApiError):
    """Exception raised when reservation fails"""
    def __init__(self, message="Failed to reserve room, it might be unavailable"):
        self.message = message
        super().__init__(self.message)


class FailedToDelChosen(ApiError):
    """Exception raised when cancellation fails"""
    def __init__(self, message="Failed to cancel reservation, it might be too late"):
        self.message = message
        super().__init__(self.message)


class FailedToFind(ApiError):
    """Exception raised when a room is not found"""
    def __init__(self, message="Room not found in the database"):
        self.message = message
        super().__init__(self.message)


class ReservationLimitExceeded(ApiError):
    """Exception raised when a user exceeds their daily reservation limit"""
    def __init__(self, message="Daily reservation limit exceeded"):
        self.message = message
        super().__init__(self.message)


class DurationLimitExceeded(ApiError):
    """Exception raised when a reservation exceeds the maximum duration"""
    def __init__(self, message="Reservation duration exceeds the maximum allowed"):
        self.message = message
        super().__init__(self.message)