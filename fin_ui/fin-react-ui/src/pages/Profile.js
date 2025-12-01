import React, { useState } from 'react';
import { Paper, Typography, Stack, Avatar, IconButton, Divider, Button, Dialog, DialogTitle, DialogContent, DialogActions, TextField, Box, Switch, FormControlLabel } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import LockIcon from '@mui/icons-material/Lock';
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive';
import EmailIcon from '@mui/icons-material/Email';
import SmsIcon from '@mui/icons-material/Sms';
import { getUserInfo } from '../utils/auth';
import UserLayout from '../components/UserLayout';

export default function UserProfile() {
  const userInfo = getUserInfo();
  const [editProfileOpen, setEditProfileOpen] = useState(false);
  const [editPasswordOpen, setEditPasswordOpen] = useState(false);
  const [profileForm, setProfileForm] = useState({
    username: userInfo?.user?.username || '',
    email: userInfo?.user?.email || '',
    phone: userInfo?.user?.phone || ''
  });
  const [passwordForm, setPasswordForm] = useState({
    oldPassword: '',
    newPassword: '',
    confirmPassword: ''
  });
  const [notifSettings, setNotifSettings] = useState({
    push: userInfo?.settings?.push || false,
    email: userInfo?.settings?.email || false,
    sms: userInfo?.settings?.sms || false
  });

  // Handlers for profile edit
  const handleProfileChange = e => {
    setProfileForm({ ...profileForm, [e.target.name]: e.target.value });
  };
  const handlePasswordChange = e => {
    setPasswordForm({ ...passwordForm, [e.target.name]: e.target.value });
  };
  const handleNotifChange = e => {
    setNotifSettings({ ...notifSettings, [e.target.name]: e.target.checked });
    // TODO: Call PUT API to update settings
  };

  // Dummy submit handlers
  const handleProfileSubmit = () => {
    // TODO: Call PUT API to update profile
    setEditProfileOpen(false);
  };
  const handlePasswordSubmit = () => {
    // TODO: Call PUT API to update password
    setEditPasswordOpen(false);
  };

  return (
    <UserLayout>
      <Paper elevation={3} sx={{padding:4, maxWidth:1200, margin:'40px auto'}}>
        <Typography variant="h5" gutterBottom>User Profile</Typography>
        <Stack direction="row" spacing={3} alignItems="center" sx={{ mb: 4 }}>
          <Avatar sx={{ width: 80, height: 80 }} />
          <Box>
            <Typography variant="h6">{profileForm.username}</Typography>
            <Typography variant="body2">{profileForm.email}</Typography>
            <Typography variant="body2">{profileForm.phone}</Typography>
          </Box>
          <IconButton onClick={() => setEditProfileOpen(true)}><EditIcon /></IconButton>
        </Stack>
        <Divider sx={{ mb: 4 }} />
        <Typography variant="h6" sx={{ mb: 2 }}>Notification Settings</Typography>
        <Stack direction="row" spacing={2}>
          <FormControlLabel control={<Switch checked={notifSettings.push} onChange={handleNotifChange} name="push" />} label={<NotificationsActiveIcon />} />
          <FormControlLabel control={<Switch checked={notifSettings.email} onChange={handleNotifChange} name="email" />} label={<EmailIcon />} />
          <FormControlLabel control={<Switch checked={notifSettings.sms} onChange={handleNotifChange} name="sms" />} label={<SmsIcon />} />
        </Stack>
        <Box sx={{ mt: 4 }}>
          <Button variant="contained" startIcon={<LockIcon />} onClick={() => setEditPasswordOpen(true)}>
            Change Password
          </Button>
        </Box>
        {/* Edit Profile Dialog */}
        <Dialog open={editProfileOpen} onClose={() => setEditProfileOpen(false)}>
          <DialogTitle>Edit Profile</DialogTitle>
          <DialogContent>
            <TextField margin="dense" label="Username" name="username" value={profileForm.username} onChange={handleProfileChange} fullWidth />
            <TextField margin="dense" label="Email" name="email" value={profileForm.email} onChange={handleProfileChange} fullWidth />
            <TextField margin="dense" label="Phone" name="phone" value={profileForm.phone} onChange={handleProfileChange} fullWidth />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setEditProfileOpen(false)}>Cancel</Button>
            <Button onClick={handleProfileSubmit} variant="contained">Save</Button>
          </DialogActions>
        </Dialog>
        {/* Edit Password Dialog */}
        <Dialog open={editPasswordOpen} onClose={() => setEditPasswordOpen(false)}>
          <DialogTitle>Change Password</DialogTitle>
          <DialogContent>
            <TextField margin="dense" label="Old Password" name="oldPassword" type="password" value={passwordForm.oldPassword} onChange={handlePasswordChange} fullWidth />
            <TextField margin="dense" label="New Password" name="newPassword" type="password" value={passwordForm.newPassword} onChange={handlePasswordChange} fullWidth />
            <TextField margin="dense" label="Confirm Password" name="confirmPassword" type="password" value={passwordForm.confirmPassword} onChange={handlePasswordChange} fullWidth />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setEditPasswordOpen(false)}>Cancel</Button>
            <Button onClick={handlePasswordSubmit} variant="contained">Change</Button>
          </DialogActions>
        </Dialog>
      </Paper>
    </UserLayout>
  );
}
