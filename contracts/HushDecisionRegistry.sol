// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title HUSH Decision Registry
/// @notice Stores provenance only. Raw constraints and salts must never be submitted.
contract HushDecisionRegistry {
    address public immutable relayer;

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
    mapping(bytes32 => bytes32) public conditionCommitments;

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
    error AlreadyExists();
    error RecordMismatch();

    modifier onlyRelayer() {
        if (msg.sender != relayer) revert Unauthorized();
        _;
    }

    constructor(address relayer_) {
        if (relayer_ == address(0)) revert Unauthorized();
        relayer = relayer_;
    }

    function createDecision(bytes32 decisionRoomId) external onlyRelayer {
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
        if (conditionCommitments[constraintVersionId] != bytes32(0)) revert AlreadyExists();
        conditionCommitments[constraintVersionId] = conditionCommitment;
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
        if (conditionCommitments[previousConstraintVersionId] != previousConditionCommitment) revert RecordMismatch();
        if (conditionCommitments[newConstraintVersionId] != bytes32(0)) revert AlreadyExists();
        if (newConstraintVersion <= previousConstraintVersion) revert InvalidState();
        conditionCommitments[newConstraintVersionId] = newConditionCommitment;
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
        record.inputFinalized = true;
        record.inputSetRoot = inputSetRoot;
        record.candidateDatasetHash = candidateDatasetHash;
        record.engineVersion = engineVersion;
        record.engineCodeHash = engineCodeHash;
        emit InputSetFinalized(decisionRoomId, inputSetRoot);
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
        if (
            record.inputSetRoot != inputSetRoot ||
            record.candidateDatasetHash != candidateDatasetHash ||
            record.engineCodeHash != engineCodeHash
        ) revert RecordMismatch();
        record.finalDecisionHash = finalDecisionHash;
        record.decisionCommitment = decisionCommitment;
        record.decisionCommitted = true;
        emit DecisionCommitted(decisionRoomId, decisionCommitment);
    }

    function verifyDecisionRecord(bytes32 decisionRoomId) external view returns (DecisionRecord memory) {
        return decisions[decisionRoomId];
    }
}
