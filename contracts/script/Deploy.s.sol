// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/LendingPool.sol";
import "../src/MockERC20.sol";
import "../src/MockPriceOracle.sol";

contract Deploy is Script {
    function run() external {
        vm.startBroadcast();

        MockERC20 wbtc = new MockERC20("Mock Wrapped Bitcoin", "mWBTC", 18);
        MockERC20 debt = new MockERC20("Mock USD Coin", "mUSDC", 18);
        MockPriceOracle oracle = new MockPriceOracle();

        // address(0) = native ETH @ $2000, mWBTC @ $60000, mUSDC @ $1
        oracle.setPrice(address(0),    2_000e18);
        oracle.setPrice(address(wbtc), 60_000e18);
        oracle.setPrice(address(debt), 1e18);

        LendingPool pool = new LendingPool(address(debt), address(oracle));
        pool.addCollateralToken(address(wbtc));

        // Seed pool with borrowable mUSDC
        debt.mint(address(pool), 1_000_000e18);

        // Mint mWBTC to all 10 default Anvil accounts
        address[10] memory accounts = [
            0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266,
            0x70997970C51812dc3A010C7d01b50e0d17dc79C8,
            0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC,
            0x90F79bf6EB2c4f870365E785982E1f101E93b906,
            0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65,
            0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc,
            0x976EA74026E726554dB657fA54763abd0C3a0aa9,
            0x14dC79964da2C08b23698B3D3cc7Ca32193d9955,
            0x23618e81E3f5cdF7f54C3d65f7FBc0aBf5B21E8f,
            0xa0Ee7A142d267C1f36714E4a8F75612F20a79720
        ];
        for (uint256 i = 0; i < accounts.length; i++) {
            wbtc.mint(accounts[i], 10e18);
        }

        vm.stopBroadcast();
    }
}
