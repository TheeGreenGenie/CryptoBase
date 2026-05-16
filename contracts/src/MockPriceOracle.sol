// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract MockPriceOracle {
    address public owner;
    mapping(address => uint256) public priceUsdE18;

    event PriceUpdated(address indexed asset, uint256 priceUsdE18);

    error NotOwner();
    error MissingPrice();

    constructor() {
        owner = msg.sender;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    function setPrice(address asset, uint256 price) external onlyOwner {
        priceUsdE18[asset] = price;
        emit PriceUpdated(asset, price);
    }

    function getPrice(address asset) external view returns (uint256) {
        uint256 price = priceUsdE18[asset];
        if (price == 0) revert MissingPrice();
        return price;
    }
}
