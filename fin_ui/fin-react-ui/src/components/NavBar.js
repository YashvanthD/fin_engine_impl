import React from 'react';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import AccountCircle from '@mui/icons-material/AccountCircle';
import Avatar from '@mui/material/Avatar';
import { Link, useNavigate } from 'react-router-dom';
import { getUserInfo, removeUserInfo } from '../utils/auth';

export default function NavBar() {
  const [anchorEl, setAnchorEl] = React.useState(null);
  const open = Boolean(anchorEl);
  const navigate = useNavigate();

  // Get user info and role
  const userInfo = getUserInfo();
  const loggedIn = !!userInfo;

  const handleMenu = (event) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };

  // Profile menu actions
  const handleProfileAction = (action) => {
    handleClose();
    if (action === 'logout') {
      removeUserInfo();
      console.log('[NavBar Debug] User logged out');
      navigate('/login');
    }
    if (action === 'profile') navigate('/users/profile');
    if (action === 'settings') navigate('/settings');
    if (action === 'theme') navigate('/theme');
    if (action === 'login') navigate('/login');
    if (action === 'signup') navigate('/register');
  };

  return (
    <AppBar position="fixed" color="primary" sx={{ top: 0, zIndex: (theme) => theme.zIndex.drawer + 1 }}>
      <Toolbar>
        <Typography variant="h6" component={Link} to="/" sx={{ flexGrow: 1, textDecoration: 'none', color: 'inherit' }}>
          Fin Engine
        </Typography>
        {/* Removed Home and Tasks buttons, navigation is now in SideNav */}
        <IconButton
          size="large"
          edge="end"
          color="inherit"
          onClick={handleMenu}
          sx={{ ml: 2 }}
        >
          {loggedIn ? <Avatar alt="Profile" /> : <AccountCircle />}
        </IconButton>
        {loggedIn && (
          <Button
            color="inherit"
            sx={{ ml: 2 }}
            onClick={() => handleProfileAction('logout')}
          >
            Logout
          </Button>
        )}
        <Menu
          anchorEl={anchorEl}
          open={open}
          onClose={handleClose}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
          sx={{ '& .MuiPaper-root': { minWidth: 220, p: 1 } }}
        >
          {loggedIn ? (
            [
              <MenuItem key="profile" onClick={() => handleProfileAction('profile')}>Profile</MenuItem>,
              <MenuItem key="settings" onClick={() => handleProfileAction('settings')}>Settings</MenuItem>,
              <MenuItem key="theme" onClick={() => handleProfileAction('theme')}>Theme</MenuItem>,
              <MenuItem key="logout" onClick={() => handleProfileAction('logout')}>Logout</MenuItem>
            ]
          ) : (
            [
              <MenuItem key="login" onClick={() => handleProfileAction('login')}>Login</MenuItem>,
              <MenuItem key="signup" onClick={() => handleProfileAction('signup')}>Sign Up</MenuItem>
            ]
          )}
        </Menu>
      </Toolbar>
    </AppBar>
  );
}
