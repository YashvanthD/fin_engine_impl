import React, { useEffect, useState } from 'react';
import {
  Paper, Typography, Button, TextField, Stack, CircularProgress, Avatar, Divider
} from '@mui/material';
import UserLayout from '../../components/UserLayout';
import { getUserInfo } from '../../utils/auth';
import { apiFetch } from '../../utils/api';

export default function Profile() {
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editMode, setEditMode] = useState(false);
  const [form, setForm] = useState({});
  const [error, setError] = useState('');
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
          setForm(data.profile);
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

  const handleEdit = () => setEditMode(true);
  const handleCancel = () => {
    setEditMode(false);
    setForm(profile);
    setError('');
  };
  const handleChange = (e) => {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }));
  };
  const handleSave = async () => {
    setError('');
    try {
      const res = await apiFetch('/user/profile', {
        method: 'PUT',
        body: JSON.stringify(form),
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setProfile({ ...profile, ...form });
        setEditMode(false);
      } else {
        setError(data.error || 'Failed to update profile');
      }
    } catch (err) {
      setError('Network/server error');
    }
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
      <Paper sx={{ p: 4, maxWidth: 500, m: '40px auto', borderRadius: 3, boxShadow: 6 }}>
        <Stack alignItems="center" spacing={2} mb={2}>
          <Avatar sx={{ width: 80, height: 80 }} />
          <Typography variant="h5" fontWeight={700}>{profile?.username || 'User'}</Typography>
          <Typography variant="body2" color="text.secondary">{profile?.email}</Typography>
        </Stack>
        <Divider sx={{ mb: 2 }} />
        {editMode ? (
          <Stack spacing={2}>
            <TextField label="First Name" name="first_name" value={form.first_name || ''} onChange={handleChange} fullWidth />
            <TextField label="Last Name" name="last_name" value={form.last_name || ''} onChange={handleChange} fullWidth />
            <TextField label="DOB" name="dob" value={form.dob || ''} onChange={handleChange} fullWidth />
            <TextField label="Address 1" name="address1" value={form.address1 || ''} onChange={handleChange} fullWidth />
            <TextField label="Address 2" name="address2" value={form.address2 || ''} onChange={handleChange} fullWidth />
            <TextField label="Pincode" name="pincode" value={form.pincode || ''} onChange={handleChange} fullWidth />
            <TextField label="Timezone" name="timezone" value={form.timezone || ''} onChange={handleChange} fullWidth />
            {error && <Typography color="error">{error}</Typography>}
            <Stack direction="row" spacing={2} mt={2}>
              <Button variant="contained" color="primary" onClick={handleSave}>Save</Button>
              <Button variant="outlined" onClick={handleCancel}>Cancel</Button>
            </Stack>
          </Stack>
        ) : (
          <Stack spacing={2}>
            <Typography><strong>First Name:</strong> {profile?.first_name || '-'}</Typography>
            <Typography><strong>Last Name:</strong> {profile?.last_name || '-'}</Typography>
            <Typography><strong>DOB:</strong> {profile?.dob || '-'}</Typography>
            <Typography><strong>Address 1:</strong> {profile?.address1 || '-'}</Typography>
            <Typography><strong>Address 2:</strong> {profile?.address2 || '-'}</Typography>
            <Typography><strong>Pincode:</strong> {profile?.pincode || '-'}</Typography>
            <Typography><strong>Timezone:</strong> {profile?.timezone || '-'}</Typography>
            <Stack direction="row" spacing={2} mt={2}>
              <Button variant="contained" color="primary" onClick={handleEdit}>Edit</Button>
            </Stack>
          </Stack>
        )}
      </Paper>
    </UserLayout>
  );
}
