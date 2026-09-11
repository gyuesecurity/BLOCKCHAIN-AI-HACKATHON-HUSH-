// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title HUSH Decision Registry
/// @notice Stores provenance only. Raw constraints and salts must never be submitted.
contract HushDecisionRegistry {
    bytes32 private constant DECISION_DOMAIN = keccak256("HUSH_DECISION_V1");
    address public immutable relayer;

    struct ConditionRecord {
        bool exists;
        bytes32 decisionRoomId;
        bytes32 participantPseudonym;
        uint32 constraintVersion;
        bytes32 commitment;
        bytes32 supersededBy;
    }

    struct DecisionRecord {
        bool created;
        bool inputFinalized;
        bool decisionCommitted;
        bytes32 inputSetRoot;
        bytes32 candidateDatasetHash;
        bytes32 engineCodeHash;
        bytes32 finalDecisionHash;
        bytes32 decisionCommitment;
        string engineVersion;
    }

    mapping(bytes32 => DecisionRecord) private decisions;
    mapping(bytes32 => ConditionRecord) private conditions;

    event DecisionCreated(bytes32 indexed decisionRoomId);
    event ConditionCommitted(
        bytes32 indexed decisionRoomId,
        bytes32 indexed participantPseudonym,
        bytes32 indexed constraintVersionId,
        uint32 constraintVersion,
        bytes32 conditionCommitment
    );
    event ConditionSuperseded(
        bytes32 indexed decisionRoomId,
        bytes32 indexed participantPseudonym,
        bytes32 previousConstraintVersionId,
        uint32 previousConstraintVersion,
        bytes32 previousConditionCommitment,
        bytes32 newConstraintVersionId,
        uint32 newConstraintVersion,
        bytes32 newConditionCommitment
    );
    event InputSetFinalized(bytes32 indexed decisionRoomId, bytes32 inputSetRoot);
    event DecisionCommitted(bytes32 indexed decisionRoomId, bytes32 decisionCommitment);

    error Unauthorized();
    error InvalidState();
    error InvalidValue();
    error AlreadyExists();
    error RecordMismatch();

    modifier onlyRelayer() {
        if (msg.sender != relayer) revert Unauthorized();
        _;
    }

    constructor(address relayer_) {
        if (relayer_ == address(0)) revert InvalidValue();
        relayer = relayer_;
    }

    function createDecision(bytes32 decisionRoomId) external onlyRelayer {
        if (decisionRoomId == bytes32(0)) revert InvalidValue();
        if (decisions[decisionRoomId].created) revert AlreadyExists();
        decisions[decisionRoomId].created = true;
        emit DecisionCreated(decisionRoomId);
    }

    function commitCondition(
        bytes32 decisionRoomId,
        bytes32 participantPseudonym,
        bytes32 constraintVersionId,
        uint32 constraintVersion,
        bytes32 conditionCommitment
    ) external onlyRelayer {
        if (!decisions[decisionRoomId].created) revert InvalidState();
        if (
            participantPseudonym == bytes32(0) ||
            constraintVersionId == bytes32(0) ||
            constraintVersion == 0 ||
            conditionCommitment == bytes32(0)
        ) revert InvalidValue();
        if (conditions[constraintVersionId].exists) revert AlreadyExists();
        conditions[constraintVersionId] = ConditionRecord({
            exists: true,
            decisionRoomId: decisionRoomId,
            participantPseudonym: participantPseudonym,
            constraintVersion: constraintVersion,
            commitment: conditionCommitment,
            supersededBy: bytes32(0)
        });
        emit ConditionCommitted(decisionRoomId, participantPseudonym, constraintVersionId, constraintVersion, conditionCommitment);
    }

    function supersedeCondition(
        bytes32 decisionRoomId,
        bytes32 participantPseudonym,
        bytes32 previousConstraintVersionId,
        uint32 previousConstraintVersion,
        bytes32 previousConditionCommitment,
        bytes32 newConstraintVersionId,
        uint32 newConstraintVersion,
        bytes32 newConditionCommitment
    ) external onlyRelayer {
        if (!decisions[decisionRoomId].created) revert InvalidState();
        if (newConstraintVersionId == bytes32(0) || newConditionCommitment == bytes32(0)) revert InvalidValue();
        ConditionRecord storage previous = conditions[previousConstraintVersionId];
        if (
            !previous.exists ||
            previous.decisionRoomId != decisionRoomId ||
            previous.participantPseudonym != participantPseudonym ||
            previous.constraintVersion != previousConstraintVersion ||
            previous.commitment != previousConditionCommitment
        ) revert RecordMismatch();
        if (previous.supersededBy != bytes32(0)) revert InvalidState();
        if (conditions[newConstraintVersionId].exists) revert AlreadyExists();
        if (newConstraintVersion != previousConstraintVersion + 1) revert InvalidValue();

        conditions[newConstraintVersionId] = ConditionRecord({
            exists: true,
            decisionRoomId: decisionRoomId,
            participantPseudonym: participantPseudonym,
            constraintVersion: newConstraintVersion,
            commitment: newConditionCommitment,
            supersededBy: bytes32(0)
        });
        previous.supersededBy = newConstraintVersionId;
        emit ConditionSuperseded(
            decisionRoomId,
            participantPseudonym,
            previousConstraintVersionId,
            previousConstraintVersion,
            previousConditionCommitment,
            newConstraintVersionId,
            newConstraintVersion,
            newConditionCommitment
        );
    }

    function finalizeInputSet(
        bytes32 decisionRoomId,
        bytes32 inputSetRoot,
        bytes32 candidateDatasetHash,
        string calldata engineVersion,
        bytes32 engineCodeHash
    ) external onlyRelayer {
        DecisionRecord storage record = decisions[decisionRoomId];
        if (!record.created || record.inputFinalized) revert InvalidState();
        if (
            inputSetRoot == bytes32(0) ||
            candidateDatasetHash == bytes32(0) ||
            bytes(engineVersion).length == 0 ||
            engineCodeHash == bytes32(0)
        ) revert InvalidValue();
        record.inputFinalized = true;
        record.inputSetRoot = inputSetRoot;
        record.candidateDatasetHash = candidateDatasetHash;
        record.engineVersion = engineVersion;
        record.engineCodeHash = engineCodeHash;
        emit InputSetFinalized(decisionRoomId, inputSetRoot);
    }

    function computeDecisionCommitment(
        bytes32 decisionRoomId,
        bytes32 inputSetRoot,
        bytes32 candidateDatasetHash,
        string memory engineVersion,
        bytes32 engineCodeHash,
        bytes32 finalDecisionHash
    ) public view returns (bytes32) {
        return keccak256(
            abi.encode(
                DECISION_DOMAIN,
                block.chainid,
                address(this),
                decisionRoomId,
                inputSetRoot,
                candidateDatasetHash,
                keccak256(bytes(engineVersion)),
                engineCodeHash,
                finalDecisionHash
            )
        );
    }

    function commitDecision(
        bytes32 decisionRoomId,
        bytes32 inputSetRoot,
        bytes32 candidateDatasetHash,
        bytes32 engineCodeHash,
        bytes32 finalDecisionHash,
        bytes32 decisionCommitment
    ) external onlyRelayer {
        DecisionRecord storage record = decisions[decisionRoomId];
        if (!record.inputFinalized || record.decisionCommitted) revert InvalidState();
        if (finalDecisionHash == bytes32(0) || decisionCommitment == bytes32(0)) revert InvalidValue();
        if (
            record.inputSetRoot != inputSetRoot ||
            record.candidateDatasetHash != candidateDatasetHash ||
            record.engineCodeHash != engineCodeHash
        ) revert RecordMismatch();
        bytes32 expected = computeDecisionCommitment(
            decisionRoomId,
            inputSetRoot,
            candidateDatasetHash,
            record.engineVersion,
            engineCodeHash,
            finalDecisionHash
        );
        if (decisionCommitment != expected) revert RecordMismatch();
        record.finalDecisionHash = finalDecisionHash;
        record.decisionCommitment = decisionCommitment;
        record.decisionCommitted = true;
        emit DecisionCommitted(decisionRoomId, decisionCommitment);
    }

    function conditionRecord(bytes32 constraintVersionId) external view returns (ConditionRecord memory) {
        return conditions[constraintVersionId];
    }

    function verifyDecisionRecord(bytes32 decisionRoomId) external view returns (DecisionRecord memory) {
        return decisions[decisionRoomId];
    }
}
