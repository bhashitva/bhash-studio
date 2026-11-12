# Hindi project formats version 1

## Configuration

`परियोजना.भाषविन्यास` uses JSON structure with Bhash's existing unquoted literals `सत्य`, `असत्य` and `रिक्त`. They decode to booleans and null. Strings containing those words remain strings. English literal spellings and alternate yes/no terms are rejected outside strings. Numbers follow JSON syntax and must be finite. Strings use JSON escapes. Configuration keys are normalized to NFC and duplicate normalized keys fail. User strings are preserved. Nesting is limited to 64 levels.

```text
{
  "योजना_संस्करण": 1,
  "नाम": "मेरा ऐप",
  "लक्ष्य": "एंड्रॉयड",
  "ऐप_पहचान": "org.bhashitva.app0123456789",
  "न्यूनतम_एंड्रॉयड_स्तर": 29,
  "संजाल_अनुमति": असत्य,
  "प्रारंभिक_मान": रिक्त
}
```

| Field | Type and constraint |
| --- | --- |
| योजना_संस्करण | Integer 1 |
| नाम | Nonempty display string up to 100 characters |
| लक्ष्य | एंड्रॉयड, डेस्कटॉप or वेब. Android is implemented. |
| ऐप_पहचान | Stable ASCII Android application ID, generated once at creation |
| न्यूनतम_एंड्रॉयड_स्तर | Integer 29 for this prototype |
| संजाल_अनुमति | Boolean. Maps to INTERNET permission when true. |
| प्रारंभिक_मान | Optional reserved application data. Parsed and preserved, with no runtime behavior yet. |

All fields except प्रारंभिक_मान are required and unknown fields fail. Omitted optional fields remain absent. Explicit रिक्त remains null. A reserved value must never silently turn into a string or a default. The editor blocks changing an existing application ID while saving.

## Screen XML

The root is `पर्दा` with `पहचान="मुख्य"` and a nonempty `शीर्षक`. It contains one `स्तंभ` or `पंक्ति`. Containers may nest. Unknown tags and attributes fail. XML entities for literal text such as `&amp;` and `&quot;` work. DTDs, comments and declarations with `<!` are rejected. At most 200 components and 12 nested container levels are accepted.

| Component | Authored behavior |
| --- | --- |
| `पाठ` | Displays its text. An optional `पहचान` makes it a result target and permits empty initial text. |
| `प्रविष्टि` | Single-line text input. Its body is the visible label. Requires `पहचान` and accepts optional `आरंभिक` text. |
| `बटन` | Its body is the label and `दबानेपर` names the Bhash handler. `इनपुटसे` reads the identified input at click time. `परिणाममें` writes the returned text to the identified `पाठ`. |

Component IDs are NFC-normalized, unique within the screen and checked by component kind. Live input requires an explicit result target. `तर्क` supplies a literal argument and cannot be combined with `इनपुटसे`. Existing literal buttons without `परिणाममें` still display results in the shared footer. When neither input nor literal is provided, the argument is empty. Inputs and named text values survive configuration changes and ordinary activity recreation. They are not stored as application data across cold starts.

Handlers currently use `फलन नाम(मान: पाठ) -> पाठ`. Export symbols are deterministic ASCII names assigned by traversal order within a build. They are internal implementation details. Bhash's compiler validates exported types and function resolution during compilation. The preliminary editor signature check is intentionally limited and can reject unusual formatting or accept a signature-looking comment. Full compiler validation is the build gate.

## Compatibility

The configuration is a JSON dialect and requires the studio parser. Standard JSON parsers cannot read its unquoted Hindi literals. Standard JSON or Android XML is generated only for integration. Future schema migrations must preserve application IDs, user strings and explicit null values. New schema versions must be rejected by older studios with Hindi recovery guidance before modifying files.
