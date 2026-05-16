// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

interface IERC20Like {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
}

interface IPriceOracle {
    function getPrice(address asset) external view returns (uint256);
}

contract LendingPool {
    uint256 public constant BPS = 10_000;
    uint256 public constant MIN_COLLATERAL_RATIO_BPS = 15_000;
    uint256 public constant LIQUIDATION_THRESHOLD_BPS = 12_500;
    uint256 public constant LIQUIDATION_BONUS_BPS = 500;
    uint256 public constant WAD = 1e18;

    // address(0) is the sentinel for native ETH in all mappings and oracle lookups
    address public constant ETH = address(0);

    IERC20Like public immutable debtToken;
    IPriceOracle public immutable oracle;
    address public immutable owner;

    // collateralBalance[user][token] — token==address(0) means ETH
    mapping(address => mapping(address => uint256)) public collateralBalance;
    mapping(address => uint256) public debtBalance;

    // registered ERC20 collateral tokens (ETH is always supported implicitly)
    address[] public collateralTokenList;
    mapping(address => bool) public isCollateral;

    uint256 private locked;

    event Supplied(address indexed user, address indexed token, uint256 amount);
    event Withdrawn(address indexed user, address indexed token, uint256 amount);
    event Borrowed(address indexed user, uint256 amount);
    event Repaid(address indexed user, uint256 amount);
    event Liquidated(address indexed liquidator, address indexed borrower, uint256 repayAmount);

    error AmountZero();
    error TransferFailed();
    error InsufficientCollateral();
    error UnsupportedToken();
    error HealthyPosition();
    error ReentrantCall();
    error NotOwner();

    modifier nonReentrant() {
        if (locked == 1) revert ReentrantCall();
        locked = 1;
        _;
        locked = 0;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(address debtToken_, address oracle_) {
        debtToken = IERC20Like(debtToken_);
        oracle = IPriceOracle(oracle_);
        owner = msg.sender;
    }

    function addCollateralToken(address token) external onlyOwner {
        if (!isCollateral[token]) {
            isCollateral[token] = true;
            collateralTokenList.push(token);
        }
    }

    // Supply native ETH — pass token = address(0), amount ignored, use msg.value
    // Supply ERC20   — pass token = ERC20 address, amount = token amount
    function supply(address token, uint256 amount) external payable nonReentrant {
        if (token == ETH) {
            if (msg.value == 0) revert AmountZero();
            collateralBalance[msg.sender][ETH] += msg.value;
            emit Supplied(msg.sender, ETH, msg.value);
        } else {
            if (!isCollateral[token]) revert UnsupportedToken();
            if (amount == 0) revert AmountZero();
            collateralBalance[msg.sender][token] += amount;
            if (!IERC20Like(token).transferFrom(msg.sender, address(this), amount)) revert TransferFailed();
            emit Supplied(msg.sender, token, amount);
        }
    }

    function withdraw(address token, uint256 amount) external nonReentrant {
        if (amount == 0) revert AmountZero();
        uint256 current = collateralBalance[msg.sender][token];
        if (current < amount) revert InsufficientCollateral();
        collateralBalance[msg.sender][token] = current - amount;
        if (!_isCollateralized(msg.sender, MIN_COLLATERAL_RATIO_BPS)) revert InsufficientCollateral();
        if (token == ETH) {
            (bool ok, ) = payable(msg.sender).call{value: amount}("");
            if (!ok) revert TransferFailed();
        } else {
            if (!IERC20Like(token).transfer(msg.sender, amount)) revert TransferFailed();
        }
        emit Withdrawn(msg.sender, token, amount);
    }

    function borrow(uint256 amount) external nonReentrant {
        if (amount == 0) revert AmountZero();
        debtBalance[msg.sender] += amount;
        if (!_isCollateralized(msg.sender, MIN_COLLATERAL_RATIO_BPS)) revert InsufficientCollateral();
        if (!debtToken.transfer(msg.sender, amount)) revert TransferFailed();
        emit Borrowed(msg.sender, amount);
    }

    function repay(uint256 amount) external nonReentrant {
        if (amount == 0) revert AmountZero();
        uint256 currentDebt = debtBalance[msg.sender];
        uint256 repayAmount = amount > currentDebt ? currentDebt : amount;
        debtBalance[msg.sender] = currentDebt - repayAmount;
        if (!debtToken.transferFrom(msg.sender, address(this), repayAmount)) revert TransferFailed();
        emit Repaid(msg.sender, repayAmount);
    }

    function healthFactor(address user) external view returns (uint256) {
        uint256 debtValue = debtValueUsd(user);
        if (debtValue == 0) return type(uint256).max;
        return (collateralValueUsd(user) * LIQUIDATION_THRESHOLD_BPS * WAD) / (debtValue * BPS);
    }

    function collateralValueUsd(address user) public view returns (uint256) {
        uint256 total = (collateralBalance[user][ETH] * oracle.getPrice(ETH)) / WAD;
        for (uint256 i = 0; i < collateralTokenList.length; i++) {
            address t = collateralTokenList[i];
            total += (collateralBalance[user][t] * oracle.getPrice(t)) / WAD;
        }
        return total;
    }

    function debtValueUsd(address user) public view returns (uint256) {
        return (debtBalance[user] * oracle.getPrice(address(debtToken))) / WAD;
    }

    function collateralTokenCount() external view returns (uint256) {
        return collateralTokenList.length;
    }

    function _isCollateralized(address user, uint256 requiredRatioBps) internal view returns (bool) {
        uint256 debtValue = debtValueUsd(user);
        if (debtValue == 0) return true;
        return collateralValueUsd(user) * BPS >= debtValue * requiredRatioBps;
    }

    receive() external payable {}
}
