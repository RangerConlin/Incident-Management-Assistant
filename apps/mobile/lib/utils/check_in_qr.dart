/// The personal check-in QR code payload.
///
/// A check-in desk (the desktop app's Quick Check In window) reads this to
/// find the person. The format must stay in step with
/// `modules/logistics/checkin/qr_code.py` in the desktop repo. It is a plain
/// prefixed string rather than JSON because hardware QR scanners usually act
/// as keyboards, and braces/quotes are what keyboard layouts mangle most.
/// Only the visible Person ID is encoded; the desk resolves it against the
/// roster.
class CheckInQr {
  CheckInQr._();

  static const prefix = 'SARAPP:CHECKIN:v1:';

  static String payload(String personId) => '$prefix${personId.trim()}';
}
