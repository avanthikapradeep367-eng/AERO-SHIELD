// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title   EvidenceVault
 * @author  AERO-SHIELD X — Blockchain & Digital Forensics Module
 * @notice  Immutable on-chain trust layer for the AERO-SHIELD X Aerospace Cyber
 *          Defense Platform. Four independent modules share a single deployed address:
 *
 *            Module 1 — Device Registry       : register and track aerospace hardware
 *            Module 2 — Authentication Ledger : permanent log of rolling-key auth events
 *            Module 3 — Evidence Vault        : cryptographic anchoring of cyber incidents
 *            Module 4 — Threat Intelligence   : malicious-device blacklist + risk profiles
 *
 *          Integration partners:
 *            Member 1 — Rolling Key Authentication  →  writes to Module 2
 *            Member 3 — SentinelX AI + CUDA         →  writes to Module 3 & Module 4
 *
 * @dev     Inherits OpenZeppelin Ownable v5. The deploying account becomes the
 *          initial owner and is the sole entity authorised to call any write
 *          function. Ownership may be transferred post-deployment.
 *
 *          All read functions are unrestricted (public / external view).
 *          All write functions require msg.sender == owner().
 *
 *          Constructor takes no arguments so the existing deploy.js script
 *          requires no modifications.
 */
contract EvidenceVault is Ownable {

    // ====================================================================
    //  CONSTANTS — Status Codes
    //  Named uint8 constants are used instead of enums to keep the ABI
    //  simple and to allow direct uint8 comparisons without casting.
    // ====================================================================

    // ---- Authentication Status -----------------------------------------

    /// @notice Rolling-key authentication attempt failed.
    uint8 public constant AUTH_FAILED  = 0;

    /// @notice Rolling-key authentication attempt succeeded.
    uint8 public constant AUTH_SUCCESS = 1;

    // ---- Incident Status -----------------------------------------------

    /// @notice Incident recorded; awaiting triage.
    uint8 public constant INCIDENT_OPEN          = 0;

    /// @notice Incident is under active investigation.
    uint8 public constant INCIDENT_INVESTIGATING = 1;

    /// @notice Incident has been mitigated; resolution confirmed.
    uint8 public constant INCIDENT_RESOLVED      = 2;

    /// @notice Incident lifecycle is complete; no further action required.
    uint8 public constant INCIDENT_CLOSED        = 3;

    // ====================================================================
    //  STRUCTS
    // ====================================================================

    /**
     * @dev Represents a physical or virtual aerospace entity participating in
     *      the AERO-SHIELD X communication network.
     *
     *      Covered entities: UAVs, manned aircraft, ground control stations,
     *      satellite gateways, and IoT edge nodes.
     *
     *      Storage packing note:
     *        address owner   (20 bytes)
     *        bool    active  ( 1 byte ) ─── packed into the same 32-byte slot
     *        bool    exists  ( 1 byte ) ─── packed into the same 32-byte slot
     *      This saves one SSTORE compared to placing them in individual slots.
     */
    struct DeviceRecord {
        string  deviceId;       // Human-readable unique identifier — e.g. "UAV-ALPHA-001"
        string  deviceType;     // Aerospace entity category: "UAV" | "AIRCRAFT" | "GROUND_STATION" | "SATELLITE_GW" | "IOT_NODE"
        string  publicKey;      // Hex-encoded public key used by Member 1's rolling-key authentication
        address owner;          // Ethereum address of the device operator (msg.sender at registration)
        bool    active;         // Operational flag: true = live, false = decommissioned / suspended
        uint256 registeredAt;   // Block timestamp at registration — immutable after creation
        uint256 updatedAt;      // Block timestamp of the most recent status change
        bool    exists;         // Internal guard flag: enables O(1) duplicate-registration check
    }

    /**
     * @dev Immutable log entry for a single rolling-key authentication event.
     *      Written exclusively by Member 1's Rolling Key Authentication backend.
     *      Once created, an AuthRecord is never modified — every attempt
     *      (success or failure) becomes a permanent, auditable chain entry.
     *
     *      Storage packing note:
     *        uint32 rollingKeyVersion  (4 bytes)
     *        uint8  authStatus         (1 byte ) ─── packed together
     *        bool   exists             (1 byte ) ─── packed together
     */
    struct AuthRecord {
        bytes32 authenticationId;   // Caller-supplied unique identifier for this auth event
        bytes32 deviceId;           // Device that attempted authentication
        bytes32 sessionId;          // Session handle / token for this connection
        uint256 timestamp;          // Block timestamp when this record was anchored (immutable)
        uint32  rollingKeyVersion;  // Version counter of the rotating key that was used
        uint8   authStatus;         // AUTH_SUCCESS | AUTH_FAILED
        bool    exists;             // Guard flag: prevents duplicate recording in O(1)
    }

    /**
     * @dev Permanent forensic record for a cyber incident detected by
     *      SentinelX AI (Member 3).
     *
     *      IMMUTABILITY GUARANTEE:
     *        `evidenceHash` is set once in recordIncident() and no function
     *        in this contract can ever overwrite it. Any tampering with the
     *        underlying evidence artefact will produce a divergent hash,
     *        making falsification immediately detectable on-chain.
     *
     *      Storage packing note:
     *        uint8 riskScore     (1 byte)
     *        uint8 aiConfidence  (1 byte) ─── packed together
     *        uint8 status        (1 byte) ─── packed together
     *        bool  exists        (1 byte) ─── packed together
     */
    struct IncidentRecord {
        bytes32 incidentId;    // Caller-supplied unique identifier for this incident
        bytes32 sourceDevice;  // Device ID of the attacker / origin node
        bytes32 targetDevice;  // Device ID of the victim / targeted node
        bytes32 evidenceHash;  // SHA-256 digest of the raw evidence artefact — SEALED AT CREATION
        uint256 timestamp;     // Block timestamp when the record was anchored (immutable)
        string  attackType;    // "SPOOFING"|"JAMMING"|"MALWARE"|"INTRUSION"|"ANOMALY"
        string  actionTaken;   // Description of the automated or manual response taken
        uint8   riskScore;     // Threat severity 0–100 as assessed by SentinelX AI
        uint8   aiConfidence;  // SentinelX model confidence score 0–100
        uint8   status;        // INCIDENT_OPEN | INVESTIGATING | RESOLVED | CLOSED
        bool    exists;        // Guard flag: prevents duplicate recording in O(1)
    }

    /**
     * @dev Input bundle for recordIncident().
     *      Grouping the 8 incident fields into a single calldata struct reduces
     *      the external function's parameter count from 8 to 1, keeping the
     *      EVM stack well under the 16-slot limit of the legacy code generator.
     *      This is the standard pattern for high-arity functions in production
     *      Solidity without requiring the viaIR pipeline.
     */
    struct IncidentInput {
        bytes32 incidentId;    // Unique identifier for this incident
        string  attackType;    // "SPOOFING"|"JAMMING"|"MALWARE"|"INTRUSION"|"ANOMALY"
        bytes32 sourceDevice;  // Device ID of the attacker / origin node
        bytes32 targetDevice;  // Device ID of the victim / targeted node
        uint8   riskScore;     // Severity 0–100 (SentinelX AI)
        uint8   aiConfidence;  // Model confidence 0–100 (SentinelX AI)
        string  actionTaken;   // Description of the automated or manual response
        bytes32 evidenceHash;  // SHA-256 digest of the raw evidence artefact
    }

    /**
     * @dev Risk and reputation profile for a device flagged as malicious or
     *      suspicious by SentinelX AI (Member 3).
     *
     *      Storage packing note:
     *        uint8 threatLevel  (1 byte)
     *        uint8 riskScore    (1 byte) ─── packed together
     *        bool  blacklisted  (1 byte) ─── packed together
     *        bool  exists       (1 byte) ─── packed together
     */
    struct ThreatProfile {
        bytes32 deviceId;     // Device under threat monitoring
        uint256 attackCount;  // Cumulative attack events attributed to this device
        uint256 lastSeen;     // Block timestamp of the most recent malicious activity
        uint8   threatLevel;  // Severity: 0 (no threat) – 10 (critical)
        uint8   riskScore;    // Composite risk score: 0–100
        bool    blacklisted;  // True while the device is actively quarantined
        bool    exists;       // Differentiates "not yet seen" from "threat level 0"
    }

    // ====================================================================
    //  MAPPINGS
    // ====================================================================

    /**
     * @dev Module 1 — primary Device Registry lookup.
     *      Key   → string deviceId  (e.g., "UAV-ALPHA-001")
     *      Value → DeviceRecord struct
     *      Why mapping: O(1) existence check and full record retrieval by
     *      human-readable ID without iterating the _deviceIds array.
     */
    mapping(string => DeviceRecord) private _devices;

    /**
     * @dev Module 1 — registered device owner index.
     *      Key   → address (device operator's Ethereum address)
     *      Value → bool    (true once the address has registered ≥ 1 device)
     *      Why mapping: O(1) check of whether an address holds registered devices —
     *      used for ownership-scoped access control without looping over arrays.
     */
    mapping(address => bool) private _registeredOwners;

    /**
     * @dev Module 2 — primary Authentication Ledger lookup.
     *      Key → bytes32 authenticationId | Value → AuthRecord
     *      Why mapping: instant retrieval of any historical auth event by
     *      its unique ID without iterating _authIds.
     */
    mapping(bytes32 => AuthRecord) private _authRecords;

    /**
     * @dev Module 2 — per-device authentication history index.
     *      Key → bytes32 deviceId | Value → bytes32[] authenticationIds
     *      Why: allows Member 1's backend to pull the complete auth trail
     *      for any device in a single call without scanning all records.
     */
    mapping(bytes32 => bytes32[]) private _deviceAuthHistory;

    /**
     * @dev Module 3 — primary Evidence Vault lookup.
     *      Key → bytes32 incidentId | Value → IncidentRecord
     *      Why mapping: O(1) incident retrieval and duplicate-prevention check.
     */
    mapping(bytes32 => IncidentRecord) private _incidents;

    /**
     * @dev Module 4 — primary Threat Intelligence lookup.
     *      Key → bytes32 deviceId | Value → ThreatProfile
     *      Why mapping: O(1) blacklist check — isBlacklisted() is on the hot
     *      path for every device interaction across the system.
     */
    mapping(bytes32 => ThreatProfile) private _threatProfiles;

    // ====================================================================
    //  ARRAYS — Enumeration Indices
    //  These arrays exist only for counting and ordered iteration.
    //  All primary lookups use the mappings above (O(1) access).
    // ====================================================================

    /// @dev Ordered registry of all registered device IDs (string).
    ///      Each entry mirrors a key in _devices.
    ///      Used for enumeration via getRegisteredDevices() and counting via totalDevices().
    string[] private _deviceIds;

    /// @dev Ordered log of all authentication record IDs.
    bytes32[] private _authIds;

    /// @dev Ordered log of all incident IDs; last element is the most recent.
    bytes32[] private _incidentIds;

    /// @dev Ordered list of device IDs that have an associated threat profile.
    bytes32[] private _threatDeviceIds;

    // ====================================================================
    //  EVENTS
    // ====================================================================

    /**
     * @dev Emitted when a new aerospace entity is successfully registered.
     *      Indexing on `deviceId` stores keccak256(abi.encode(deviceId)) in
     *      the topic, allowing precise log filters by exact ID string.
     * @param deviceId   Human-readable unique identifier of the registered entity.
     * @param deviceType Aerospace entity category.
     * @param owner      Ethereum address of the device operator.
     * @param timestamp  Block timestamp of registration.
     */
    event DeviceRegistered(
        string  indexed deviceId,
        string          deviceType,
        address indexed owner,
        uint256         timestamp
    );

    /**
     * @dev Emitted on every status change — a unified audit signal for
     *      dashboards that want a single event per update regardless of direction.
     *      DeviceActivated or DeviceDeactivated are also emitted for targeted filtering.
     * @param deviceId  Human-readable identifier of the updated device.
     * @param active    New operational status (true = active, false = inactive).
     * @param timestamp Block timestamp of the status change.
     */
    event DeviceUpdated(
        string  indexed deviceId,
        bool            active,
        uint256         timestamp
    );

    /**
     * @dev Emitted specifically when a device's status transitions to active.
     *      Dedicated topic for operational monitoring systems that track
     *      real-time device availability in the aerospace network.
     * @param deviceId  Human-readable identifier of the activated device.
     * @param by        Address that triggered the activation (msg.sender).
     * @param timestamp Block timestamp of the activation.
     */
    event DeviceActivated(
        string  indexed deviceId,
        address indexed by,
        uint256         timestamp
    );

    /**
     * @dev Emitted specifically when a device's status transitions to inactive.
     *      Dedicated topic for incident-response systems that must react
     *      immediately when an aerospace node is taken offline.
     * @param deviceId  Human-readable identifier of the deactivated device.
     * @param by        Address that triggered the deactivation (msg.sender).
     * @param timestamp Block timestamp of the deactivation.
     */
    event DeviceDeactivated(
        string  indexed deviceId,
        address indexed by,
        uint256         timestamp
    );

    /**
     * @dev Emitted for every rolling-key authentication event (success or failure).
     *      Indexing on both authenticationId and deviceId allows event-log filters
     *      scoped to a single device without scanning the entire chain history.
     * @param authenticationId Unique identifier of this auth record.
     * @param deviceId         Device that was authenticated.
     * @param authStatus       AUTH_SUCCESS or AUTH_FAILED.
     * @param rollingKeyVersion Key version that was used / attempted.
     * @param timestamp        Block timestamp of the event.
     */
    event AuthenticationRecorded(
        bytes32 indexed authenticationId,
        bytes32 indexed deviceId,
        uint8           authStatus,
        uint32          rollingKeyVersion,
        uint256         timestamp
    );

    /**
     * @dev Dedicated failure event — provides a distinct topic filter for
     *      incident-response tooling watching for brute-force or replay
     *      attack patterns on the chain.
     * @param authenticationId Unique ID of the failed auth record.
     * @param deviceId         Device whose authentication failed.
     * @param rollingKeyVersion Key version that was rejected.
     */
    event AuthenticationFailed(
        bytes32 indexed authenticationId,
        bytes32 indexed deviceId,
        uint32          rollingKeyVersion
    );

    /**
     * @dev Emitted when a cyber incident is permanently anchored on-chain.
     *      Indexing on evidenceHash allows off-chain systems to query whether
     *      a specific piece of evidence has already been recorded.
     * @param incidentId   Unique identifier of the incident.
     * @param attackType   Attack category detected by SentinelX AI.
     * @param riskScore    Severity score provided by SentinelX AI.
     * @param aiConfidence Model confidence score provided by SentinelX AI.
     * @param evidenceHash SHA-256 hash of the sealed evidence artefact.
     * @param timestamp    Block timestamp when the record was created.
     */
    event IncidentRecorded(
        bytes32 indexed incidentId,
        string          attackType,
        uint8           riskScore,
        uint8           aiConfidence,
        bytes32 indexed evidenceHash,
        uint256         timestamp
    );

    /**
     * @dev Emitted when an incident's lifecycle status advances.
     *      evidenceHash is deliberately absent to reinforce its immutability —
     *      only the mutable status field changes.
     * @param incidentId Unique identifier of the incident.
     * @param oldStatus  Previous lifecycle status.
     * @param newStatus  New lifecycle status.
     */
    event IncidentUpdated(
        bytes32 indexed incidentId,
        uint8           oldStatus,
        uint8           newStatus
    );

    /**
     * @dev Emitted when a device is added to the threat blacklist.
     * @param deviceId    Identifier of the blacklisted device.
     * @param threatLevel Assigned threat level (0–10).
     * @param riskScore   Composite risk score (0–100).
     * @param timestamp   Block timestamp of blacklisting.
     */
    event DeviceBlacklisted(
        bytes32 indexed deviceId,
        uint8           threatLevel,
        uint8           riskScore,
        uint256         timestamp
    );

    /**
     * @dev Emitted when a device's blacklist status is cleared.
     *      The underlying ThreatProfile is preserved for historical auditing.
     * @param deviceId  Identifier of the device that was cleared.
     * @param timestamp Block timestamp of removal.
     */
    event DeviceRemoved(
        bytes32 indexed deviceId,
        uint256         timestamp
    );

    /**
     * @dev Emitted when SentinelX AI updates an existing threat profile
     *      after detecting new malicious activity from a known device.
     * @param deviceId    Identifier of the updated device.
     * @param attackCount Updated cumulative attack count.
     * @param lastSeen    Block timestamp of the most recent malicious activity.
     * @param riskScore   Updated composite risk score.
     */
    event ThreatProfileUpdated(
        bytes32 indexed deviceId,
        uint256         attackCount,
        uint256         lastSeen,
        uint8           riskScore
    );

    // ====================================================================
    //  CONSTRUCTOR
    // ====================================================================

    /**
     * @dev Passes msg.sender to OZ Ownable v5 as the initial owner.
     *      No constructor arguments are required, so the existing
     *      deploy.js script (`Factory.deploy()`) works without modification.
     */
    constructor() Ownable(msg.sender) {}

    // ====================================================================
    //  MODIFIERS
    // ====================================================================

    /**
     * @dev Reverts if `value` is bytes32(0).
     *      Prevents callers from passing uninitialised identifiers that
     *      would silently collide with mapping default values.
     * @param value The bytes32 identifier to validate.
     */
    modifier notZeroBytes32(bytes32 value) {
        require(value != bytes32(0), "EvidenceVault: identifier cannot be zero bytes");
        _;
    }

    /**
     * @dev Reverts if `score` exceeds 100.
     *      Enforces the 0–100 percentage range for riskScore and aiConfidence
     *      fields, preventing out-of-range values from corrupting analytics.
     * @param score The uint8 score to validate.
     */
    modifier validScore(uint8 score) {
        require(score <= 100, "EvidenceVault: score must be 0-100");
        _;
    }

    /**
     * @dev Reverts if `level` exceeds 10.
     *      Enforces the 0–10 range used for ThreatProfile.threatLevel so that
     *      external dashboards can rely on a fixed upper bound.
     * @param level The uint8 threat level to validate.
     */
    modifier validThreatLevel(uint8 level) {
        require(level <= 10, "EvidenceVault: threat level must be 0-10");
        _;
    }

    /**
     * @dev Reverts if `status` exceeds INCIDENT_CLOSED (3).
     *      Prevents undocumented lifecycle codes from entering the vault,
     *      which would cause incident-status dashboards to display garbage.
     * @param status The uint8 incident status to validate.
     */
    modifier validIncidentStatus(uint8 status) {
        require(status <= INCIDENT_CLOSED, "EvidenceVault: invalid incident status code");
        _;
    }

    // ====================================================================
    //  MODULE 1 — DEVICE REGISTRY
    // ====================================================================

    /**
     * @notice Register a new aerospace entity on the AERO-SHIELD X network.
     * @dev    Only the contract owner (backend service account) may call this.
     *         The device is registered as active (active = true) immediately.
     *         The caller's address (msg.sender) is recorded as the device owner
     *         and marked in _registeredOwners.
     *
     *         Reverts if:
     *           • deviceId is already registered  (prevents duplicate entries)
     *           • any string argument is empty     (prevents corrupt records)
     *
     * @param deviceId   Human-readable unique identifier — e.g. "UAV-ALPHA-001".
     * @param deviceType Aerospace entity category: "UAV" | "AIRCRAFT" |
     *                   "GROUND_STATION" | "SATELLITE_GW" | "IOT_NODE".
     * @param publicKey  Hex-encoded public key used by Member 1's rolling-key auth.
     */
    function registerDevice(
        string calldata deviceId,
        string calldata deviceType,
        string calldata publicKey
    )
        external
        onlyOwner
    {
        require(bytes(deviceId).length   > 0, "EvidenceVault: deviceId cannot be empty");
        require(bytes(deviceType).length > 0, "EvidenceVault: deviceType cannot be empty");
        require(bytes(publicKey).length  > 0, "EvidenceVault: publicKey cannot be empty");
        require(!_devices[deviceId].exists,   "EvidenceVault: device is already registered");

        // Write fields individually via storage pointer to stay within the
        // EVM 16-slot stack limit (string parameters + struct literal = overflow).
        DeviceRecord storage rec = _devices[deviceId];
        rec.deviceId     = deviceId;
        rec.deviceType   = deviceType;
        rec.publicKey    = publicKey;
        rec.owner        = msg.sender;
        rec.active       = true;
        rec.registeredAt = block.timestamp;
        rec.updatedAt    = block.timestamp;
        rec.exists       = true;

        _deviceIds.push(deviceId);
        _registeredOwners[msg.sender] = true;

        emit DeviceRegistered(deviceId, deviceType, msg.sender, block.timestamp);
    }

    /**
     * @notice Enable or disable an aerospace entity in the registry.
     * @dev    Sets active = newStatus and stamps updatedAt with the current
     *         block timestamp. Emits the unified DeviceUpdated event plus a
     *         dedicated DeviceActivated or DeviceDeactivated event so that
     *         monitoring systems can subscribe to a single, precise topic.
     *
     *         Reverts if deviceId is empty or the device has not been registered.
     *
     * @param deviceId  Human-readable identifier of the device to update.
     * @param newStatus true = activate the device; false = deactivate the device.
     */
    function updateDeviceStatus(string calldata deviceId, bool newStatus)
        external
        onlyOwner
    {
        require(bytes(deviceId).length > 0, "EvidenceVault: deviceId cannot be empty");
        require(_devices[deviceId].exists,  "EvidenceVault: device not found");

        _devices[deviceId].active    = newStatus;
        _devices[deviceId].updatedAt = block.timestamp;

        emit DeviceUpdated(deviceId, newStatus, block.timestamp);

        if (newStatus) {
            emit DeviceActivated(deviceId, msg.sender, block.timestamp);
        } else {
            emit DeviceDeactivated(deviceId, msg.sender, block.timestamp);
        }
    }

    /**
     * @notice Retrieve the complete record for a registered aerospace entity.
     * @dev    Returns a memory copy of the DeviceRecord struct.
     *         Reverts if the deviceId is empty or has never been registered.
     *
     * @param  deviceId  Human-readable identifier of the device.
     * @return           DeviceRecord struct copied to memory.
     */
    function getDevice(string calldata deviceId)
        external
        view
        returns (DeviceRecord memory)
    {
        require(bytes(deviceId).length > 0, "EvidenceVault: deviceId cannot be empty");
        require(_devices[deviceId].exists,  "EvidenceVault: device not found");
        return _devices[deviceId];
    }

    /**
     * @notice Check whether an aerospace entity has been registered.
     * @dev    Public so external contracts and off-chain callers can perform
     *         existence checks without fetching the full struct.
     *
     * @param  deviceId  Human-readable identifier to check.
     * @return           True if the device exists in the registry.
     */
    function deviceExists(string calldata deviceId) public view returns (bool) {
        return _devices[deviceId].exists;
    }

    /**
     * @notice Check whether an Ethereum address has registered at least one device.
     * @dev    O(1) lookup via _registeredOwners mapping.
     *
     * @param  account  Address to check.
     * @return          True if the address has registered one or more devices.
     */
    function isRegisteredOwner(address account) external view returns (bool) {
        return _registeredOwners[account];
    }

    // ====================================================================
    //  MODULE 2 — AUTHENTICATION LEDGER
    // ====================================================================

    /**
     * @notice Anchor a rolling-key authentication event on-chain.
     * @dev    Creates an immutable AuthRecord. Intended to be called by
     *         Member 1's Rolling Key Authentication backend after every
     *         authentication attempt — whether it succeeded or failed.
     *
     *         When authStatus == AUTH_FAILED, a dedicated AuthenticationFailed
     *         event is emitted in addition to AuthenticationRecorded, providing
     *         a filtered topic for intrusion-detection monitoring systems.
     *
     *         Reverts if authenticationId has already been recorded (guarantees
     *         exactly-once semantics for each auth event identifier).
     *
     * @param authenticationId Unique identifier for this authentication event.
     * @param deviceId         Device that attempted authentication.
     * @param rollingKeyVersion Version counter of the rotating key used.
     * @param authStatus       AUTH_SUCCESS (1) or AUTH_FAILED (0).
     * @param sessionId        Session handle / token for this connection.
     */
    function recordAuthentication(
        bytes32 authenticationId,
        bytes32 deviceId,
        uint32  rollingKeyVersion,
        uint8   authStatus,
        bytes32 sessionId
    )
        external
        onlyOwner
        notZeroBytes32(authenticationId)
        notZeroBytes32(deviceId)
    {
        require(
            authStatus == AUTH_SUCCESS || authStatus == AUTH_FAILED,
            "EvidenceVault: authStatus must be AUTH_FAILED (0) or AUTH_SUCCESS (1)"
        );
        require(
            !_authRecords[authenticationId].exists,
            "EvidenceVault: authentication record already exists"
        );

        _authRecords[authenticationId] = AuthRecord({
            authenticationId : authenticationId,
            deviceId         : deviceId,
            sessionId        : sessionId,
            timestamp        : block.timestamp,
            rollingKeyVersion: rollingKeyVersion,
            authStatus       : authStatus,
            exists           : true
        });

        _authIds.push(authenticationId);
        _deviceAuthHistory[deviceId].push(authenticationId);

        emit AuthenticationRecorded(
            authenticationId,
            deviceId,
            authStatus,
            rollingKeyVersion,
            block.timestamp
        );

        // Emit the dedicated failure signal for intrusion-detection tooling.
        if (authStatus == AUTH_FAILED) {
            emit AuthenticationFailed(authenticationId, deviceId, rollingKeyVersion);
        }
    }

    /**
     * @notice Retrieve a single authentication record by its ID.
     * @dev    Returns a memory copy of the AuthRecord struct.
     *         Reverts if the record does not exist.
     *
     * @param  authenticationId Unique identifier of the auth record.
     * @return                  AuthRecord struct copied to memory.
     */
    function getAuthentication(bytes32 authenticationId)
        external
        view
        notZeroBytes32(authenticationId)
        returns (AuthRecord memory)
    {
        require(
            _authRecords[authenticationId].exists,
            "EvidenceVault: authentication record not found"
        );
        return _authRecords[authenticationId];
    }

    /**
     * @notice Retrieve the full chronological authentication history for a device.
     * @dev    Returns the ordered array of authenticationIds from
     *         _deviceAuthHistory[deviceId]. Returns an empty array (not a revert)
     *         if the device has no recorded authentication events yet.
     *
     * @param  deviceId  Identifier of the device.
     * @return           Array of authenticationIds in chronological order.
     */
    function getAuthenticationHistory(bytes32 deviceId)
        external
        view
        notZeroBytes32(deviceId)
        returns (bytes32[] memory)
    {
        return _deviceAuthHistory[deviceId];
    }

    // ====================================================================
    //  MODULE 3 — EVIDENCE VAULT
    // ====================================================================

    /**
     * @notice Permanently anchor a cyber incident detected by SentinelX AI.
     * @dev    Only the contract owner may call this function.
     *
     *         EVIDENCE IMMUTABILITY:
     *           input.evidenceHash is written once here and is not accessible
     *           to any update function. updateIncidentStatus() only touches
     *           the `status` field. This design guarantees that the
     *           cryptographic anchor of the evidence artefact remains
     *           tamper-proof for the lifetime of the contract.
     *
     *         Reverts if input.incidentId already exists — enforces
     *         exactly-once semantics so a single incident cannot be
     *         recorded twice.
     *
     *         STACK NOTE: Parameters are wrapped in IncidentInput calldata
     *         to reduce the function's parameter count from 8 to 1, keeping
     *         the EVM stack under the 16-slot limit of the legacy code
     *         generator without requiring viaIR.
     *
     * @param input IncidentInput calldata struct containing all incident fields.
     */
    function recordIncident(IncidentInput calldata input)
        external
        onlyOwner
    {
        require(input.incidentId   != bytes32(0), "EvidenceVault: incidentId cannot be zero bytes");
        require(input.evidenceHash != bytes32(0), "EvidenceVault: evidenceHash cannot be zero bytes");
        require(input.riskScore    <= 100,         "EvidenceVault: riskScore must be 0-100");
        require(input.aiConfidence <= 100,         "EvidenceVault: aiConfidence must be 0-100");
        require(bytes(input.attackType).length  > 0, "EvidenceVault: attackType cannot be empty");
        require(bytes(input.actionTaken).length > 0, "EvidenceVault: actionTaken cannot be empty");
        require(!_incidents[input.incidentId].exists, "EvidenceVault: incident already recorded");

        IncidentRecord storage rec = _incidents[input.incidentId];
        rec.incidentId   = input.incidentId;
        rec.sourceDevice = input.sourceDevice;
        rec.targetDevice = input.targetDevice;
        rec.evidenceHash = input.evidenceHash;   // sealed — never updated after this line
        rec.timestamp    = block.timestamp;
        rec.attackType   = input.attackType;
        rec.actionTaken  = input.actionTaken;
        rec.riskScore    = input.riskScore;
        rec.aiConfidence = input.aiConfidence;
        rec.status       = INCIDENT_OPEN;
        rec.exists       = true;

        _incidentIds.push(input.incidentId);

        emit IncidentRecorded(
            input.incidentId,
            input.attackType,
            input.riskScore,
            input.aiConfidence,
            input.evidenceHash,
            block.timestamp
        );
    }

    /**
     * @notice Advance the lifecycle status of a recorded incident.
     * @dev    Modifies ONLY the `status` field. Every other field —
     *         including evidenceHash — is immutable after recordIncident().
     *         Reverts if the incident does not exist or the status code
     *         is out of range.
     *
     * @param incidentId Identifier of the incident to update.
     * @param newStatus  INCIDENT_OPEN(0)|INVESTIGATING(1)|RESOLVED(2)|CLOSED(3).
     */
    function updateIncidentStatus(bytes32 incidentId, uint8 newStatus)
        external
        onlyOwner
        notZeroBytes32(incidentId)
        validIncidentStatus(newStatus)
    {
        require(_incidents[incidentId].exists, "EvidenceVault: incident not found");

        uint8 oldStatus = _incidents[incidentId].status;
        _incidents[incidentId].status = newStatus;

        emit IncidentUpdated(incidentId, oldStatus, newStatus);
    }

    /**
     * @notice Retrieve the full forensic record for an incident.
     * @dev    Returns a memory copy of the IncidentRecord struct including
     *         the sealed evidenceHash.
     *         Reverts if the incident has not been recorded.
     *
     * @param  incidentId  Unique identifier of the incident.
     * @return             IncidentRecord struct copied to memory.
     */
    function getIncident(bytes32 incidentId)
        external
        view
        notZeroBytes32(incidentId)
        returns (IncidentRecord memory)
    {
        require(_incidents[incidentId].exists, "EvidenceVault: incident not found");
        return _incidents[incidentId];
    }

    /**
     * @notice Check whether an incident has been recorded in the vault.
     * @dev    Public so external contracts can verify incident existence
     *         without fetching the full struct.
     *
     * @param  incidentId  Identifier to check.
     * @return             True if the incident exists in the vault.
     */
    function incidentExists(bytes32 incidentId) public view returns (bool) {
        return _incidents[incidentId].exists;
    }

    // ====================================================================
    //  MODULE 4 — THREAT INTELLIGENCE
    // ====================================================================

    /**
     * @notice Add a device to the threat blacklist with an initial risk profile.
     * @dev    If the device has no prior ThreatProfile, a new one is created
     *         with attackCount = 1 and lastSeen = block.timestamp.
     *         If the device already has a ThreatProfile (previously cleared or
     *         re-detected), the existing record is updated and re-blacklisted —
     *         preserving the historical attackCount as a running total.
     *
     * @param deviceId    Identifier of the device to blacklist.
     * @param threatLevel Initial or updated threat level: 0–10.
     * @param riskScore   Initial or updated composite risk score: 0–100.
     */
    function blacklistDevice(
        bytes32 deviceId,
        uint8   threatLevel,
        uint8   riskScore
    )
        external
        onlyOwner
        notZeroBytes32(deviceId)
        validThreatLevel(threatLevel)
        validScore(riskScore)
    {
        if (!_threatProfiles[deviceId].exists) {
            _threatProfiles[deviceId] = ThreatProfile({
                deviceId    : deviceId,
                attackCount : 1,
                lastSeen    : block.timestamp,
                threatLevel : threatLevel,
                riskScore   : riskScore,
                blacklisted : true,
                exists      : true
            });
            _threatDeviceIds.push(deviceId);
        } else {
            ThreatProfile storage profile = _threatProfiles[deviceId];
            profile.threatLevel  = threatLevel;
            profile.riskScore    = riskScore;
            profile.blacklisted  = true;
            profile.lastSeen     = block.timestamp;
            profile.attackCount += 1;
        }

        emit DeviceBlacklisted(deviceId, threatLevel, riskScore, block.timestamp);
    }

    /**
     * @notice Remove a device from the active threat blacklist.
     * @dev    Clears the `blacklisted` flag but intentionally preserves the
     *         entire ThreatProfile for historical forensic auditing — the
     *         attack history must remain immutable for chain-of-custody purposes.
     *         Reverts if no profile exists or the device is not currently blacklisted.
     *
     * @param deviceId Identifier of the device to clear.
     */
    function removeBlacklist(bytes32 deviceId)
        external
        onlyOwner
        notZeroBytes32(deviceId)
    {
        require(_threatProfiles[deviceId].exists,      "EvidenceVault: threat profile not found");
        require(_threatProfiles[deviceId].blacklisted, "EvidenceVault: device is not blacklisted");

        _threatProfiles[deviceId].blacklisted = false;

        emit DeviceRemoved(deviceId, block.timestamp);
    }

    /**
     * @notice Update the threat metrics for a device already in the registry.
     * @dev    Called by the owner when SentinelX AI observes new malicious
     *         activity from a device that already has a ThreatProfile but is
     *         not being re-blacklisted (e.g., updating scores after deeper
     *         model analysis).
     *         Reverts if no ThreatProfile exists — call blacklistDevice() first.
     *
     * @param deviceId    Identifier of the device to update.
     * @param threatLevel Updated threat level: 0–10.
     * @param attackCount Updated cumulative attack count (supplied by SentinelX AI).
     * @param riskScore   Updated composite risk score: 0–100.
     */
    function updateThreatProfile(
        bytes32 deviceId,
        uint8   threatLevel,
        uint256 attackCount,
        uint8   riskScore
    )
        external
        onlyOwner
        notZeroBytes32(deviceId)
        validThreatLevel(threatLevel)
        validScore(riskScore)
    {
        require(_threatProfiles[deviceId].exists, "EvidenceVault: threat profile not found");

        ThreatProfile storage profile = _threatProfiles[deviceId];
        profile.threatLevel = threatLevel;
        profile.attackCount = attackCount;
        profile.riskScore   = riskScore;
        profile.lastSeen    = block.timestamp;

        emit ThreatProfileUpdated(deviceId, attackCount, block.timestamp, riskScore);
    }

    /**
     * @notice Retrieve the full threat profile for a device.
     * @dev    Returns a memory copy of the ThreatProfile struct.
     *         Reverts if no threat profile has been created for this device.
     *
     * @param  deviceId  Identifier of the device.
     * @return           ThreatProfile struct copied to memory.
     */
    function getThreatProfile(bytes32 deviceId)
        external
        view
        notZeroBytes32(deviceId)
        returns (ThreatProfile memory)
    {
        require(_threatProfiles[deviceId].exists, "EvidenceVault: threat profile not found");
        return _threatProfiles[deviceId];
    }

    /**
     * @notice Check whether a device is currently on the active blacklist.
     * @dev    Returns false — not a revert — when no ThreatProfile exists,
     *         because a device that has never been seen is by definition not
     *         blacklisted. This keeps the hot-path check gas-efficient.
     *
     * @param  deviceId  Identifier of the device.
     * @return           True if the device is currently blacklisted.
     */
    function isBlacklisted(bytes32 deviceId) public view returns (bool) {
        return _threatProfiles[deviceId].blacklisted;
    }

    // ====================================================================
    //  VIEW FUNCTIONS — Statistics & Convenience
    // ====================================================================

    /**
     * @notice Total number of aerospace entities registered in Module 1.
     * @dev    Reads the length of _deviceIds — O(1), no iteration.
     * @return Count of registered devices.
     */
    function totalDevices() external view returns (uint256) {
        return _deviceIds.length;
    }

    /**
     * @notice Return the array of all registered device IDs.
     * @dev    Returns a memory copy of the full _deviceIds array.
     *         Gas cost scales linearly with the number of registered devices,
     *         so this is intended for off-chain calls only (eth_call / view).
     *         Do NOT call from a state-changing transaction.
     *
     * @return ids  String array of every registered deviceId in insertion order.
     */
    function getRegisteredDevices() external view returns (string[] memory ids) {
        return _deviceIds;
    }

    /**
     * @notice Total number of authentication records anchored in Module 2.
     * @return Count of authentication records.
     */
    function totalAuthentications() external view returns (uint256) {
        return _authIds.length;
    }

    /**
     * @notice Total number of incidents recorded in Module 3.
     * @return Count of incident records.
     */
    function totalIncidents() external view returns (uint256) {
        return _incidentIds.length;
    }

    /**
     * @notice Total number of devices with a threat profile in Module 4.
     * @return Count of devices in the threat intelligence registry.
     */
    function totalThreatDevices() external view returns (uint256) {
        return _threatDeviceIds.length;
    }

    /**
     * @notice Retrieve the most recently recorded incident.
     * @dev    Reads the last element of _incidentIds and returns the
     *         corresponding IncidentRecord from the mapping.
     *         Reverts if no incidents have been recorded yet.
     *
     * @return The most recent IncidentRecord (memory copy).
     */
    function latestIncident() external view returns (IncidentRecord memory) {
        require(_incidentIds.length > 0, "EvidenceVault: no incidents recorded");
        return _incidents[_incidentIds[_incidentIds.length - 1]];
    }

    /**
     * @notice Retrieve the most recently recorded authentication event.
     * @dev    Reads the last element of _authIds and returns the corresponding
     *         AuthRecord from the mapping.
     *         Reverts if no authentication records exist yet.
     *
     * @return The most recent AuthRecord (memory copy).
     */
    function latestAuthentication() external view returns (AuthRecord memory) {
        require(_authIds.length > 0, "EvidenceVault: no authentication records exist");
        return _authRecords[_authIds[_authIds.length - 1]];
    }

    /**
     * @notice Contract name and version identifier.
     * @dev    Updated on each phase release. Used by Web3.py and monitoring
     *         tools to verify the correct contract version is deployed.
     *
     * @return Version string for AERO-SHIELD X EvidenceVault Phase 2.
     */
    function version() external pure returns (string memory) {
        return "AERO-SHIELD-X:EvidenceVault:v2.0.0-phase2";
    }
}
