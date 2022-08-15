// SPDX-License-Identifier: UNLICENSED
// AnuuTech Ltd - BasicPP contract
pragma solidity ^0.8.0;

import "@openzeppelin/contracts/security/PullPayment.sol";

// BasicPP class using PullPayment
contract BasicPP is PullPayment {

  constructor() payable { }

  // helper function to call asyncTransfer
  function callTransfer(address dest, string calldata tx_hash) public payable {
    _asyncTransfer(dest, msg.value);
  }
}