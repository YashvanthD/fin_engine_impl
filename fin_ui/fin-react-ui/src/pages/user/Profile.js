import React, { useEffect, useState } from 'react';
import {
  Card, CardContent, CardActions, Paper, Typography, Button, TextField, Stack, CircularProgress, Avatar, Divider, IconButton, Switch, Dialog, DialogTitle, DialogContent, DialogActions, Box
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import LogoutIcon from '@mui/icons-material/Logout';
import UserLayout from '../../components/UserLayout';
import { getUserInfo, removeUserInfo } from '../../utils/auth';
import { apiFetch } from '../../utils/api';
import { useNavigate } from 'react-router-dom';

export default function Profile() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState('');
  const [pwdDialog, setPwdDialog] = useState(false);
  const [pwdForm, setPwdForm] = useState({ old_password: '', new_password: '' });
  const [pwdLoading, setPwdLoading] = useState(false);
  const [pwdError, setPwdError] = useState('');
  const [pwdSuccess, setPwdSuccess] = useState('');
  const [notifEnabled, setNotifEnabled] = useState(true);
  const [pushEnabled, setPushEnabled] = useState(true);
  const [smsEnabled, setSmsEnabled] = useState(false);
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [notifLoading, setNotifLoading] = useState(false);
  const [notifError, setNotifError] = useState('');
  const [notifSuccess, setNotifSuccess] = useState('');
  const [editDetailsMode, setEditDetailsMode] = useState(false);
  const [editDetailsForm, setEditDetailsForm] = useState({ dob: '', address1: '', address2: '', pincode: '', timezone: '' });
  const [editDetailsLoading, setEditDetailsLoading] = useState(false);
  const [editDetailsError, setEditDetailsError] = useState('');
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [otpSent, setOtpSent] = useState(false);
  const [otp, setOtp] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailError, setEmailError] = useState('');
  const [emailSuccess, setEmailSuccess] = useState('');
  const [mobileDialogOpen, setMobileDialogOpen] = useState(false);
  const [newMobile, setNewMobile] = useState('');
  const [mobileLoading, setMobileLoading] = useState(false);
  const [mobileError, setMobileError] = useState('');
  const [mobileSuccess, setMobileSuccess] = useState('');
  const navigate = useNavigate();
  const userInfo = getUserInfo();

  useEffect(() => {
    async function fetchProfile() {
      setLoading(true);
      setError('');
      try {
        const res = await apiFetch('/user/profile', { method: 'GET' });
        const data = await res.json();
        if (res.ok && data.success) {
          setProfile(data.profile);
          setEditForm(data.profile);
          setEditDetailsForm({
            dob: data.profile?.dob || '',
            address1: data.profile?.address1 || '',
            address2: data.profile?.address2 || '',
            pincode: data.profile?.pincode || '',
            timezone: data.profile?.timezone || ''
          });
        } else {
          setError(data.error || 'Failed to fetch profile');
        }
      } catch (err) {
        setError('Network/server error');
      }
      setLoading(false);
    }
    fetchProfile();
  }, []);

  // Placeholder metrics and permissions
  const metrics = {
    completed: 42,
    successRate: '88%',
    future: 'Coming soon...'
  };
  const permissions = {
    role: profile?.roles?.join(', ') || 'User',
    accessType: profile?.access_type || 'Standard',
    perms: profile?.permissions?.join(', ') || 'View, Edit'
  };
  const joinedDate = profile?.created_at ? new Date(profile.created_at).toLocaleDateString() : '2023-01-01';
  const lastLogin = profile?.last_login ? new Date(profile.last_login).toLocaleString() : '2025-12-01 09:00';

  // Edit profile handlers
  const handleEditOpen = () => {
    setEditForm(profile);
    setEditMode(true);
    setEditError('');
  };
  const handleEditChange = (e) => {
    setEditForm(f => ({ ...f, [e.target.name]: e.target.value }));
  };
  const handleEditSave = async () => {
    setEditLoading(true);
    setEditError('');
    try {
      const res = await apiFetch('/user/profile', {
        method: 'PUT',
        body: JSON.stringify(editForm),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setProfile({ ...profile, ...editForm });
        setEditMode(false);
      } else {
        setEditError(data.error || 'Failed to update profile');
      }
    } catch (err) {
      setEditError('Network/server error');
    }
    setEditLoading(false);
  };
  const handleEditCancel = () => {
    setEditMode(false);
    setEditForm(profile);
    setEditError('');
  };

  // Change password handlers
  const handlePwdOpen = () => {
    setPwdDialog(true);
    setPwdForm({ old_password: '', new_password: '' });
    setPwdError('');
    setPwdSuccess('');
  };
  const handlePwdChange = (e) => {
    setPwdForm(f => ({ ...f, [e.target.name]: e.target.value }));
  };
  const handlePwdSave = async () => {
    setPwdLoading(true);
    setPwdError('');
    setPwdSuccess('');
    try {
      const res = await apiFetch('/user/password', {
        method: 'PUT',
        body: JSON.stringify(pwdForm),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setPwdSuccess('Password updated successfully');
        setPwdDialog(false);
      } else {
        setPwdError(data.error || 'Failed to update password');
      }
    } catch (err) {
      setPwdError('Network/server error');
    }
    setPwdLoading(false);
  };

  // Logout handler
  const handleLogout = async () => {
    try {
      const res = await apiFetch('/user/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        removeUserInfo();
        navigate('/login');
      } else {
        setError(data.error || 'Failed to logout');
      }
    } catch (err) {
      setError('Network/server error');
    }
  };

  // Notification settings handler
  const handleNotifChange = async (type, value) => {
    setNotifLoading(true);
    setNotifError('');
    setNotifSuccess('');
    // Update local state immediately for responsiveness
    if (type === 'enabled') setNotifEnabled(value);
    if (type === 'push') setPushEnabled(value);
    if (type === 'sms') setSmsEnabled(value);
    if (type === 'email') setEmailEnabled(value);
    try {
      const res = await apiFetch('/user/settings/notifications', {
        method: 'PUT',
        body: JSON.stringify({ notifications: {
          enabled: type === 'enabled' ? value : notifEnabled,
          push: type === 'push' ? value : pushEnabled,
          sms: type === 'sms' ? value : smsEnabled,
          email: type === 'email' ? value : emailEnabled
        }}),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setNotifSuccess('Notification settings updated');
      } else {
        setNotifError(data.error || 'Failed to update notification settings');
      }
    } catch (err) {
      setNotifError('Network/server error');
    }
    setNotifLoading(false);
  };

  // Edit personal details handlers
  const handleEditDetailsOpen = () => {
    setEditDetailsForm({
      dob: profile?.dob || '',
      address1: profile?.address1 || '',
      address2: profile?.address2 || '',
      pincode: profile?.pincode || '',
      timezone: profile?.timezone || ''
    });
    setEditDetailsMode(true);
    setEditDetailsError('');
  };
  const handleEditDetailsChange = (e) => {
    setEditDetailsForm(f => ({ ...f, [e.target.name]: e.target.value }));
  };
  const handleEditDetailsSave = async () => {
    setEditDetailsLoading(true);
    setEditDetailsError('');
    try {
      const res = await apiFetch('/user/profile', {
        method: 'PUT',
        body: JSON.stringify(editDetailsForm),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setProfile({ ...profile, ...editDetailsForm });
        setEditDetailsMode(false);
      } else {
        setEditDetailsError(data.error || 'Failed to update details');
      }
    } catch (err) {
      setEditDetailsError('Network/server error');
    }
    setEditDetailsLoading(false);
  };
  const handleEditDetailsCancel = () => {
    setEditDetailsMode(false);
    setEditDetailsError('');
  };

  // Email update handlers
  const handleEmailDialogOpen = () => {
    setEmailDialogOpen(true);
    setNewEmail('');
    setOtp('');
    setOtpSent(false);
    setEmailError('');
    setEmailSuccess('');
  };
  const handleEmailDialogClose = () => {
    setEmailDialogOpen(false);
    setNewEmail('');
    setOtp('');
    setOtpSent(false);
    setEmailError('');
    setEmailSuccess('');
  };
  const handleSendOtp = async () => {
    setEmailLoading(true);
    setEmailError('');
    setEmailSuccess('');
    try {
      const res = await apiFetch('/user/email/send-otp', {
        method: 'POST',
        body: JSON.stringify({ email: newEmail }),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setOtpSent(true);
        setEmailSuccess('OTP sent to your new email');
      } else {
        setEmailError(data.error || 'Failed to send OTP');
      }
    } catch (err) {
      setEmailError('Network/server error');
    }
    setEmailLoading(false);
  };
  const handleVerifyOtp = async () => {
    setEmailLoading(true);
    setEmailError('');
    setEmailSuccess('');
    try {
      const res = await apiFetch('/user/email/verify-otp', {
        method: 'POST',
        body: JSON.stringify({ email: newEmail, otp }),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setEmailSuccess('Email updated successfully');
        setEmailDialogOpen(false);
        setProfile({ ...profile, email: newEmail });
      } else {
        setEmailError(data.error || 'Failed to verify OTP');
      }
    } catch (err) {
      setEmailError('Network/server error');
    }
    setEmailLoading(false);
  };

  // Mobile update handlers
  const handleMobileDialogOpen = () => {
    setMobileDialogOpen(true);
    setNewMobile('');
    setMobileError('');
    setMobileSuccess('');
  };
  const handleMobileDialogClose = () => {
    setMobileDialogOpen(false);
    setNewMobile('');
    setMobileError('');
    setMobileSuccess('');
  };
  const handleMobileSave = async () => {
    setMobileLoading(true);
    setMobileError('');
    setMobileSuccess('');
    try {
      const res = await apiFetch('/user/profile', {
        method: 'PUT',
        body: JSON.stringify({ mobile: newMobile }),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setMobileSuccess('Mobile number updated successfully');
        setMobileDialogOpen(false);
        setProfile({ ...profile, mobile: newMobile });
      } else {
        setMobileError(data.error || 'Failed to update mobile number');
      }
    } catch (err) {
      setMobileError('Network/server error');
    }
    setMobileLoading(false);
  };

  if (loading) {
    return (
      <UserLayout>
        <Stack alignItems="center" mt={6}><CircularProgress /></Stack>
      </UserLayout>
    );
  }
  if (error) {
    return (
      <UserLayout>
        <Paper sx={{ p: 4, maxWidth: 500, m: '40px auto' }}>
          <Typography color="error">{error}</Typography>
        </Paper>
      </UserLayout>
    );
  }

  return (
    <UserLayout>
      <Stack spacing={3} sx={{ maxWidth: 500, m: '40px auto' }}>
        {/* User Info Card */}
        <Card>
          <CardContent>
            <Stack alignItems="center" spacing={2}>
              <Box sx={{ position: 'relative' }}>
                <Avatar sx={{ width: 80, height: 80 }} src={profile?.avatar_url || ''} />
                <IconButton sx={{ position: 'absolute', bottom: 0, right: 0 }} onClick={handleEditOpen}>
                  <EditIcon />
                </IconButton>
              </Box>
              <Typography variant="h5" fontWeight={700}>{profile?.username || 'User'}</Typography>
              <Stack direction="row" spacing={2} alignItems="center" justifyContent="center" sx={{ width: '100%' }}>
                <Box sx={{ minWidth: 0, flex: 1, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    {profile?.email ? profile.email : 'Email not added'}
                  </Typography>
                  {!profile?.email && (
                    <Typography variant="caption" color="primary" sx={{ cursor: 'pointer', textDecoration: 'underline' }} onClick={handleEmailDialogOpen}>
                      Update
                    </Typography>
                  )}
                </Box>
                <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
                <Box sx={{ minWidth: 0, flex: 1, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    {profile?.mobile ? profile.mobile : 'Mobile not added'}
                  </Typography>
                  {!profile?.mobile && (
                    <Typography variant="caption" color="primary" sx={{ cursor: 'pointer', textDecoration: 'underline' }} onClick={handleMobileDialogOpen}>
                      Update
                    </Typography>
                  )}
                </Box>
              </Stack>
              <Divider sx={{ my: 2 }} />
              <Stack spacing={1} alignItems="center">
                <Typography variant="body1"><strong>Joined:</strong> {joinedDate}</Typography>
                <Typography variant="body1"><strong>Last Login:</strong> {lastLogin}</Typography>
              </Stack>
            </Stack>
          </CardContent>
        </Card>
        {/* Activity Card */}
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>Your Activity</Typography>
            <Divider sx={{ mb: 2 }} />
            <Typography variant="body1">Tasks Completed: <strong>{metrics.completed}</strong></Typography>
            <Typography variant="body1">Success Rate: <strong>{metrics.successRate}</strong></Typography>
            <Typography variant="body2" color="text.secondary">{metrics.future}</Typography>
          </CardContent>
        </Card>
        {/* Address & Details Card */}
        <Card>
          <CardContent>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="h6" fontWeight={600} gutterBottom>Personal Details</Typography>
              <IconButton size="small" onClick={() => setEditDetailsMode(true)}>
                <EditIcon fontSize="small" />
              </IconButton>
            </Stack>
            <Divider sx={{ mb: 2 }} />
            <Stack spacing={1}>
              <Typography variant="body1"><strong>Date of Birth:</strong> {profile?.dob ? profile.dob : 'Not added'}</Typography>
              <Typography variant="body1"><strong>Address 1:</strong> {profile?.address1 ? profile.address1 : 'Not added'}</Typography>
              <Typography variant="body1"><strong>Address 2:</strong> {profile?.address2 ? profile.address2 : 'Not added'}</Typography>
              <Typography variant="body1"><strong>Pincode:</strong> {profile?.pincode ? profile.pincode : 'Not added'}</Typography>
              <Typography variant="body1"><strong>Timezone:</strong> {profile?.timezone ? profile.timezone : 'Not added'}</Typography>
            </Stack>
          </CardContent>
        </Card>
        {/* Permissions Card */}
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>Your Permission</Typography>
            <Stack direction="row" spacing={2} alignItems="center" justifyContent="center" sx={{ width: '100%' }}>
              <Typography variant="body2" color="text.secondary" sx={{ minWidth: 0, flex: 1, textAlign: 'center' }}>
                Account Key: <strong>{profile?.account_key || 'Not available'}</strong>
              </Typography>
              <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
              <Typography variant="body2" color="text.secondary" sx={{ minWidth: 0, flex: 1, textAlign: 'center' }}>
                User Key: <strong>{profile?.user_key || 'Not available'}</strong>
              </Typography>
            </Stack>
            <Divider sx={{ mt: 2, mb: 2 }} />
            <Typography variant="body1">Role: <strong>{permissions.role}</strong></Typography>
            <Typography variant="body1">Access Type: <strong>{permissions.accessType}</strong></Typography>
            <Typography variant="body1">Permissions: <strong>{permissions.perms}</strong></Typography>
          </CardContent>
        </Card>
        {/* Account Settings Card */}
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>Account Settings</Typography>
            <Divider sx={{ mb: 2 }} />
            <Stack direction="row" spacing={2}>
              <Button variant="contained" color="primary" onClick={handleEditOpen}>Edit Profile</Button>
              <Button variant="outlined" color="primary" onClick={handlePwdOpen}>Change Password</Button>
            </Stack>
          </CardContent>
        </Card>
        {/* Notifications Card (merged) */}
        <Card>
          <CardContent>
            <Typography variant="h6" fontWeight={600} gutterBottom>Notifications</Typography>
            <Divider sx={{ mb: 2 }} />
            <Stack direction="row" spacing={2} alignItems="center" mb={2}>
              <Typography>Enable Notifications</Typography>
              <Switch checked={notifEnabled} onChange={e => handleNotifChange('enabled', e.target.checked)} disabled={notifLoading} />
            </Stack>
            <Stack direction="row" spacing={2} alignItems="center">
              <Typography>Push</Typography>
              <Switch checked={pushEnabled} onChange={e => handleNotifChange('push', e.target.checked)} disabled={!notifEnabled || notifLoading} />
              <Typography>SMS</Typography>
              <Switch checked={smsEnabled} onChange={e => handleNotifChange('sms', e.target.checked)} disabled={!notifEnabled || notifLoading} />
              <Typography>Email</Typography>
              <Switch checked={emailEnabled} onChange={e => handleNotifChange('email', e.target.checked)} disabled={!notifEnabled || notifLoading} />
              {notifLoading && <CircularProgress size={18} />}
            </Stack>
            {notifError && <Typography color="error" variant="body2">{notifError}</Typography>}
            {notifSuccess && <Typography color="success.main" variant="body2">{notifSuccess}</Typography>}
          </CardContent>
        </Card>
        {/* Logout Card */}
        <Card>
          <CardContent>
            <Stack direction="row" spacing={2} alignItems="center" justifyContent="center">
              <Button variant="contained" color="error" startIcon={<LogoutIcon />} onClick={handleLogout}>Logout</Button>
            </Stack>
          </CardContent>
        </Card>
      </Stack>
      {/* Edit Profile Dialog */}
      <Dialog open={editMode} onClose={handleEditCancel} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Profile</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <TextField label="First Name" name="first_name" value={editForm.first_name || ''} onChange={handleEditChange} fullWidth />
            <TextField label="Last Name" name="last_name" value={editForm.last_name || ''} onChange={handleEditChange} fullWidth />
            <TextField label="DOB" name="dob" value={editForm.dob || ''} onChange={handleEditChange} fullWidth />
            <TextField label="Address 1" name="address1" value={editForm.address1 || ''} onChange={handleEditChange} fullWidth />
            <TextField label="Address 2" name="address2" value={editForm.address2 || ''} onChange={handleEditChange} fullWidth />
            <TextField label="Pincode" name="pincode" value={editForm.pincode || ''} onChange={handleEditChange} fullWidth />
            <TextField label="Timezone" name="timezone" value={editForm.timezone || ''} onChange={handleEditChange} fullWidth />
            {editError && <Typography color="error">{editError}</Typography>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleEditCancel}>Cancel</Button>
          <Button onClick={handleEditSave} variant="contained" color="primary" disabled={editLoading}>{editLoading ? <CircularProgress size={20} /> : 'Save'}</Button>
        </DialogActions>
      </Dialog>
      {/* Change Password Dialog */}
      <Dialog open={pwdDialog} onClose={() => setPwdDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Change Password</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <TextField label="Old Password" name="old_password" type="password" value={pwdForm.old_password} onChange={handlePwdChange} fullWidth />
            <TextField label="New Password" name="new_password" type="password" value={pwdForm.new_password} onChange={handlePwdChange} fullWidth />
            {pwdError && <Typography color="error">{pwdError}</Typography>}
            {pwdSuccess && <Typography color="success.main">{pwdSuccess}</Typography>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPwdDialog(false)}>Cancel</Button>
          <Button onClick={handlePwdSave} variant="contained" color="primary" disabled={pwdLoading}>{pwdLoading ? <CircularProgress size={20} /> : 'Change Password'}</Button>
        </DialogActions>
      </Dialog>
      {/* Edit Personal Details Dialog */}
      <Dialog open={editDetailsMode} onClose={handleEditDetailsCancel} maxWidth="sm" fullWidth>
        <DialogTitle>Edit Personal Details</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <TextField label="Date of Birth" name="dob" value={editDetailsForm.dob} onChange={handleEditDetailsChange} fullWidth />
            <TextField label="Address 1" name="address1" value={editDetailsForm.address1} onChange={handleEditDetailsChange} fullWidth />
            <TextField label="Address 2" name="address2" value={editDetailsForm.address2} onChange={handleEditDetailsChange} fullWidth />
            <TextField label="Pincode" name="pincode" value={editDetailsForm.pincode} onChange={handleEditDetailsChange} fullWidth />
            <TextField label="Timezone" name="timezone" value={editDetailsForm.timezone} onChange={handleEditDetailsChange} fullWidth />
            {editDetailsError && <Typography color="error">{editDetailsError}</Typography>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleEditDetailsCancel}>Cancel</Button>
          <Button onClick={handleEditDetailsSave} variant="contained" color="primary" disabled={editDetailsLoading}>{editDetailsLoading ? <CircularProgress size={20} /> : 'Save'}</Button>
        </DialogActions>
      </Dialog>
      {/* Email Update Dialog */}
      <Dialog open={emailDialogOpen} onClose={handleEmailDialogClose} maxWidth="xs" fullWidth>
        <DialogTitle>Update Email</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <TextField
              label="New Email"
              type="email"
              value={newEmail}
              onChange={e => setNewEmail(e.target.value)}
              fullWidth
              disabled={otpSent}
            />
            {!otpSent && (
              <Stack direction="row" spacing={2}>
                <Button variant="contained" color="primary" onClick={async () => {
                  setEmailLoading(true);
                  setEmailError('');
                  setEmailSuccess('');
                  try {
                    const res = await apiFetch('/user/profile', {
                      method: 'PUT',
                      body: JSON.stringify({ email: newEmail }),
                      headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                      setEmailSuccess('Email updated successfully');
                      setEmailDialogOpen(false);
                      setProfile({ ...profile, email: newEmail });
                    } else {
                      setEmailError(data.error || 'Failed to update email');
                    }
                  } catch (err) {
                    setEmailError('Network/server error');
                  }
                  setEmailLoading(false);
                }} disabled={emailLoading || !newEmail}>
                  {emailLoading ? <CircularProgress size={20} /> : 'Update'}
                </Button>
                <Button variant="outlined" color="primary" onClick={handleSendOtp} disabled={emailLoading || !newEmail}>
                  {emailLoading ? <CircularProgress size={20} /> : 'Verify with OTP'}
                </Button>
              </Stack>
            )}
            {otpSent && (
              <>
                <TextField
                  label="Enter OTP"
                  value={otp}
                  onChange={e => setOtp(e.target.value)}
                  fullWidth
                />
                <Button variant="contained" color="primary" onClick={handleVerifyOtp} disabled={emailLoading || !otp}>
                  {emailLoading ? <CircularProgress size={20} /> : 'Verify'}
                </Button>
              </>
            )}
            {emailError && <Typography color="error">{emailError}</Typography>}
            {emailSuccess && <Typography color="success.main">{emailSuccess}</Typography>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleEmailDialogClose}>Cancel</Button>
        </DialogActions>
      </Dialog>
      {/* Mobile Update Dialog */}
      <Dialog open={mobileDialogOpen} onClose={handleMobileDialogClose} maxWidth="xs" fullWidth>
        <DialogTitle>Update Mobile Number</DialogTitle>
        <DialogContent>
          <Stack spacing={2}>
            <TextField
              label="New Mobile Number"
              type="tel"
              value={newMobile}
              onChange={e => setNewMobile(e.target.value)}
              fullWidth
              disabled={otpSent}
            />
            {!otpSent && (
              <Stack direction="row" spacing={2}>
                <Button variant="contained" color="primary" onClick={handleMobileSave} disabled={mobileLoading || !newMobile}>
                  {mobileLoading ? <CircularProgress size={20} /> : 'Update'}
                </Button>
                <Button variant="outlined" color="primary" onClick={async () => {
                  setMobileLoading(true);
                  setMobileError('');
                  setMobileSuccess('');
                  try {
                    const res = await apiFetch('/user/mobile/send-otp', {
                      method: 'POST',
                      body: JSON.stringify({ mobile: newMobile }),
                      headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                      setOtpSent(true);
                      setMobileSuccess('OTP sent to your new mobile number');
                    } else {
                      setMobileError(data.error || 'Failed to send OTP');
                    }
                  } catch (err) {
                    setMobileError('Network/server error');
                  }
                  setMobileLoading(false);
                }} disabled={mobileLoading || !newMobile}>
                  {mobileLoading ? <CircularProgress size={20} /> : 'Verify with OTP'}
                </Button>
              </Stack>
            )}
            {otpSent && (
              <>
                <TextField
                  label="Enter OTP"
                  value={otp}
                  onChange={e => setOtp(e.target.value)}
                  fullWidth
                />
                <Button variant="contained" color="primary" onClick={async () => {
                  setMobileLoading(true);
                  setMobileError('');
                  setMobileSuccess('');
                  try {
                    const res = await apiFetch('/user/mobile/verify-otp', {
                      method: 'POST',
                      body: JSON.stringify({ mobile: newMobile, otp }),
                      headers: { 'Content-Type': 'application/json' }
                    });
                    const data = await res.json();
                    if (res.ok && data.success) {
                      setMobileSuccess('Mobile number verified and updated');
                      setMobileDialogOpen(false);
                      setProfile({ ...profile, mobile: newMobile });
                    } else {
                      setMobileError(data.error || 'Failed to verify OTP');
                    }
                  } catch (err) {
                    setMobileError('Network/server error');
                  }
                  setMobileLoading(false);
                }} disabled={mobileLoading || !otp}>
                  {mobileLoading ? <CircularProgress size={20} /> : 'Verify'}
                </Button>
              </>
            )}
            {mobileError && <Typography color="error">{mobileError}</Typography>}
            {mobileSuccess && <Typography color="success.main">{mobileSuccess}</Typography>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleMobileDialogClose}>Cancel</Button>
        </DialogActions>
      </Dialog>
    </UserLayout>
  );
}
