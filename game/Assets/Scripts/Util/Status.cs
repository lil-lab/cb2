using System;
namespace Util
{
    public class Status
    {
        // Taken from https://abseil.io/docs/cpp/guides/status-codes.
        public enum StatusCode : int
        {
	        OK = 1,
	        CANCELLED,
	        INVALID_ARGUMENT,
            DEADLINE_EXCEEDED,
            NOT_FOUND,
            ALREADY_EXISTS,
            PERMISSION_DENIED,
            UNAUTHENTICATED,
            RESOURCE_EXHAUSTED,
            FAILED_PRECONDITIONS,
            ABORTED,
            UNAVAILABLE,
            OUT_OF_RANGE,
            UNIMPLEMENTED,
            INTERNAL,
            DATA_LOSS,
            UNKNOWN
	    }

        StatusCode _code;
        string _message;

        // Allows for chaining statuses.
        Status _child;

        public Status(StatusCode code)
        {
            _code = code;
        }

        public Status(StatusCode code, string message)
        {
            _code = code;
            _message = message;
        }

        public bool Ok()
        {
            if (_code != StatusCode.OK)
                return false;

            // Recursively check the child status. Allows status chaining.
            if (_child != null)
            { 
                return _child.Ok(); 
	        }
            else
            {
			    return true;
	        }
	    }

        public void Chain(Status child)
        {
            _child = child;
	    }
    }
}  // namespace Util
