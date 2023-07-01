using System;
namespace Util
{

    [Serializable]
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

        public static Status OkStatus(string message = "")
        {
            return new Status(StatusCode.OK, message);
        }

        public static Status Cancelled(string message)
        {
            return new Status(StatusCode.CANCELLED, message);
        }

        public static Status InvalidArgument(string message)
        {
            return new Status(StatusCode.INVALID_ARGUMENT, message);
        }

        public static Status DeadlineExceeded(string message)
        {
            return new Status(StatusCode.DEADLINE_EXCEEDED, message);
        }

        public static Status NotFound(string message)
        {
            return new Status(StatusCode.NOT_FOUND, message);
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

        public override string ToString()
        {
            string output = "[" + _code + "]: " + _message;
            if (_child != null)
            {
                output += "\n\t" + _child.ToString();
            }
            return output;
        }

        public void Chain(Status child)
        {
            _child = child;
        }
    }
}  // namespace Util