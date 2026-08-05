// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControlUpgradeable} from "@openzeppelin/contracts-upgradeable/access/AccessControlUpgradeable.sol";
import {ERC721Upgradeable} from "@openzeppelin/contracts-upgradeable/token/ERC721/ERC721Upgradeable.sol";
import {PausableUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import {ReentrancyGuardUpgradeable} from "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import {UUPSUpgradeable} from "@openzeppelin/contracts-upgradeable/proxy/utils/UUPSUpgradeable.sol";

/// @notice Soulbound NFT that represents a time-limited paid membership.
contract SubscriptionNFT is
    ERC721Upgradeable,
    AccessControlUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    UUPSUpgradeable
{
    bytes32 public constant OPERATOR_ROLE = keccak256("OPERATOR_ROLE");

    error InvalidPrice();
    error InvalidDuration();
    error IncorrectPayment(uint256 expected, uint256 received);
    error NoMembership(address account);
    error TransfersDisabled();
    error InvalidTreasury();
    error WithdrawalFailed();
    error DirectPaymentNotAccepted();

    event SubscriptionPurchased(address indexed account, uint256 indexed tokenId, uint64 expiresAt);
    event SubscriptionExtended(address indexed account, uint256 indexed tokenId, uint64 expiresAt);
    event SubscriptionTermsUpdated(uint128 price, uint64 duration);
    event TreasuryUpdated(address indexed treasury);
    event Withdrawn(address indexed treasury, uint256 amount);

    // These variables share one storage slot, minimizing recurring subscription-state costs.
    uint128 public subscriptionPrice;
    uint64 public subscriptionDuration;
    uint64 private _nextTokenId;

    address public treasury;
    mapping(address account => uint256 tokenId) public tokenIdOf;
    mapping(uint256 tokenId => uint64 expiresAt) public expiresAt;

    /// @custom:oz-upgrades-unsafe-allow constructor
    constructor() {
        _disableInitializers();
    }

    function initialize(
        address admin,
        uint128 price,
        uint64 duration,
        string calldata name_,
        string calldata symbol_
    ) external initializer {
        if (admin == address(0)) revert InvalidTreasury();
        if (price == 0) revert InvalidPrice();
        if (duration == 0) revert InvalidDuration();

        __ERC721_init(name_, symbol_);
        __AccessControl_init();
        __Pausable_init();
        __ReentrancyGuard_init();
        __UUPSUpgradeable_init();

        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(OPERATOR_ROLE, admin);
        subscriptionPrice = price;
        subscriptionDuration = duration;
        treasury = admin;
    }

    /// @notice Buys a first membership or renews the caller's existing membership.
    function subscribe() external payable whenNotPaused nonReentrant {
        if (msg.value != subscriptionPrice) {
            revert IncorrectPayment(subscriptionPrice, msg.value);
        }

        uint256 tokenId = tokenIdOf[msg.sender];
        uint64 newExpiry;
        if (tokenId == 0) {
            tokenId = ++_nextTokenId;
            tokenIdOf[msg.sender] = tokenId;
            _safeMint(msg.sender, tokenId);

            newExpiry = uint64(block.timestamp) + subscriptionDuration;
            expiresAt[tokenId] = newExpiry;
            emit SubscriptionPurchased(msg.sender, tokenId, newExpiry);
            return;
        }

        newExpiry = _extendFromCurrentOrExpiry(tokenId, subscriptionDuration);
        emit SubscriptionExtended(msg.sender, tokenId, newExpiry);
    }

    /// @notice Lets customer-service operators extend an existing membership without payment.
    function extendMembership(address account, uint64 duration)
        external
        onlyRole(OPERATOR_ROLE)
        returns (uint64 newExpiry)
    {
        if (duration == 0) revert InvalidDuration();

        uint256 tokenId = tokenIdOf[account];
        if (tokenId == 0) revert NoMembership(account);

        newExpiry = _extendFromCurrentOrExpiry(tokenId, duration);
        emit SubscriptionExtended(account, tokenId, newExpiry);
    }

    function setSubscriptionTerms(uint128 price, uint64 duration) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (price == 0) revert InvalidPrice();
        if (duration == 0) revert InvalidDuration();

        subscriptionPrice = price;
        subscriptionDuration = duration;
        emit SubscriptionTermsUpdated(price, duration);
    }

    function setTreasury(address newTreasury) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (newTreasury == address(0)) revert InvalidTreasury();
        treasury = newTreasury;
        emit TreasuryUpdated(newTreasury);
    }

    function pause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _pause();
    }

    function unpause() external onlyRole(DEFAULT_ADMIN_ROLE) {
        _unpause();
    }

    function withdraw() external onlyRole(DEFAULT_ADMIN_ROLE) nonReentrant {
        uint256 amount = address(this).balance;
        (bool sent,) = treasury.call{value: amount}("");
        if (!sent) revert WithdrawalFailed();
        emit Withdrawn(treasury, amount);
    }

    function isActive(address account) public view returns (bool) {
        uint256 tokenId = tokenIdOf[account];
        return tokenId != 0 && expiresAt[tokenId] > block.timestamp;
    }

    function membershipOf(address account)
        external
        view
        returns (uint256 tokenId, uint64 expiry, bool active)
    {
        tokenId = tokenIdOf[account];
        expiry = tokenId == 0 ? 0 : expiresAt[tokenId];
        active = expiry > block.timestamp;
    }

    function _extendFromCurrentOrExpiry(uint256 tokenId, uint64 duration) private returns (uint64) {
        uint64 extensionStart = expiresAt[tokenId] > block.timestamp
            ? expiresAt[tokenId]
            : uint64(block.timestamp);
        return expiresAt[tokenId] = extensionStart + duration;
    }

    /// @dev Membership NFTs may be minted but never transferred between wallets.
    function _update(address to, uint256 tokenId, address auth)
        internal
        override
        returns (address)
    {
        address from = _ownerOf(tokenId);
        if (from != address(0) && to != address(0)) revert TransfersDisabled();
        return super._update(to, tokenId, auth);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721Upgradeable, AccessControlUpgradeable)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _authorizeUpgrade(address) internal override onlyRole(DEFAULT_ADMIN_ROLE) {}

    receive() external payable {
        revert DirectPaymentNotAccepted();
    }
}
