// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {SubscriptionNFT} from "../SubscriptionNFT.sol";

/// @custom:oz-upgrades-unsafe-allow missing-initializer
contract SubscriptionNFTV2 is SubscriptionNFT {
    function version() external pure returns (uint256) {
        return 2;
    }
}
