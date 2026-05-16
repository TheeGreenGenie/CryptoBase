// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/LendingPool.sol";
import "../src/MockERC20.sol";
import "../src/MockPriceOracle.sol";

contract LendingPoolTest is Test {
    MockERC20 wbtc;
    MockERC20 debt;
    MockPriceOracle oracle;
    LendingPool pool;

    address user = address(0xA11CE);
    address liquidator = address(0xB0B);

    function setUp() public {
        wbtc = new MockERC20("Mock Wrapped Bitcoin", "mWBTC", 18);
        debt = new MockERC20("Mock USD Coin", "mUSDC", 18);
        oracle = new MockPriceOracle();
        oracle.setPrice(address(0),     2_000e18);
        oracle.setPrice(address(wbtc),  60_000e18);
        oracle.setPrice(address(debt),  1e18);

        pool = new LendingPool(address(debt), address(oracle));
        pool.addCollateralToken(address(wbtc));

        debt.mint(address(pool), 1_000_000e18);
        debt.mint(liquidator, 100_000e18);

        deal(user, 100e18);
        wbtc.mint(user, 10e18);

        vm.prank(user);
        wbtc.approve(address(pool), type(uint256).max);
        vm.prank(user);
        debt.approve(address(pool), type(uint256).max);
        vm.prank(liquidator);
        debt.approve(address(pool), type(uint256).max);
    }

    function testSupplyETHIncreasesCollateral() public {
        vm.prank(user);
        pool.supply{value: 1e18}(address(0), 0);
        assertEq(pool.collateralBalance(user, address(0)), 1e18);
    }

    function testSupplyERC20IncreasesCollateral() public {
        vm.prank(user);
        pool.supply(address(wbtc), 1e18);
        assertEq(pool.collateralBalance(user, address(wbtc)), 1e18);
    }

    function testWithdrawETHDecreasesCollateral() public {
        vm.startPrank(user);
        pool.supply{value: 2e18}(address(0), 0);
        pool.withdraw(address(0), 1e18);
        vm.stopPrank();
        assertEq(pool.collateralBalance(user, address(0)), 1e18);
    }

    function testCannotWithdrawBelowRequiredCollateralRatio() public {
        vm.startPrank(user);
        pool.supply{value: 1e18}(address(0), 0);
        pool.borrow(1_000e18);
        vm.expectRevert(LendingPool.InsufficientCollateral.selector);
        pool.withdraw(address(0), 0.5e18);
        vm.stopPrank();
    }

    function testBorrowSucceedsWhenCollateralized() public {
        vm.startPrank(user);
        pool.supply{value: 1e18}(address(0), 0);
        pool.borrow(1_000e18);
        vm.stopPrank();
        assertEq(pool.debtBalance(user), 1_000e18);
    }

    function testBorrowRevertsWhenUndercollateralized() public {
        vm.startPrank(user);
        pool.supply{value: 1e18}(address(0), 0);
        vm.expectRevert(LendingPool.InsufficientCollateral.selector);
        pool.borrow(2_000e18);
        vm.stopPrank();
    }

    function testRepayDecreasesDebt() public {
        vm.startPrank(user);
        pool.supply{value: 1e18}(address(0), 0);
        pool.borrow(1_000e18);
        pool.repay(400e18);
        vm.stopPrank();
        assertEq(pool.debtBalance(user), 600e18);
    }

    function testUnsupportedTokenReverts() public {
        address fake = address(0xDEAD);
        vm.prank(user);
        vm.expectRevert(LendingPool.UnsupportedToken.selector);
        pool.supply(fake, 1e18);
    }
}
