import React, { useState } from 'react';
import {
  Card, CardContent, Typography, TextField, Button, Stack, CircularProgress, MenuItem, Select, InputLabel, FormControl, Chip
} from '@mui/material';
import { getAccessToken, getUserInfo } from '../../utils/auth';
import { apiFetch } from '../../utils/api';
import SideNav from '../../components/SideNav';

export default function AddUser() {
  const [form, setForm] = useState({
    username: '',
    email: '',
    phone: '',
    password: '',
    roles: [],
    actions: []
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const userInfo = getUserInfo();
  const accountKey = userInfo?.account_key || '';

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(f => ({ ...f, [name]: value }));
  };

  const handleRolesChange = (e) => {
    setForm(f => ({ ...f, roles: e.target.value }));
  };

  const handleActionsChange = (e) => {
    setForm(f => ({ ...f, actions: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const res = await apiFetch(`/auth/account/${accountKey}/signup`, {
        method: 'POST',
        body: JSON.stringify(form),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAccessToken()}`
        }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setSuccess('User added successfully!');
        setForm({ username: '', email: '', phone: '', password: '', roles: [], actions: [] });
      } else {
        setError(data.error || (data.errors && Object.values(data.errors).join(', ')) || 'Failed to add user');
      }
    } catch (err) {
      setError('Network/server error');
    }
    setLoading(false);
  };

  return (
    <div style={{ display: 'flex' }}>
      <SideNav selected="adduser" />
      <div style={{ flex: 1, paddingTop: '64px' }}>
        <Card sx={{ maxWidth: 500, m: '40px auto', p: 2, mt: 6 }}>
          <CardContent>
            <Typography variant="h5" fontWeight={700} gutterBottom>Add User</Typography>
            <form onSubmit={handleSubmit}>
              <Stack spacing={2}>
                <TextField label="Username" name="username" value={form.username} onChange={handleChange} required fullWidth />
                <TextField label="Email" name="email" type="email" value={form.email} onChange={handleChange} fullWidth />
                <TextField label="Phone" name="phone" type="tel" value={form.phone} onChange={handleChange} fullWidth />
                <TextField label="Password" name="password" type="password" value={form.password} onChange={handleChange} required fullWidth />
                <FormControl fullWidth required>
                  <InputLabel>Roles</InputLabel>
                  <Select
                    multiple
                    name="roles"
                    value={form.roles}
                    onChange={handleRolesChange}
                    variant="outlined"
                    renderValue={(selected) => (
                      <Stack direction="row" gap={1}>{selected.map((role) => <Chip key={role} label={role} />)}</Stack>
                    )}
                  >
                    <MenuItem value="user">User</MenuItem>
                    <MenuItem value="manager">Manager</MenuItem>
                    {/* Add more roles as needed */}
                  </Select>
                </FormControl>
                <FormControl fullWidth>
                  <InputLabel>Actions</InputLabel>
                  <Select
                    multiple
                    name="actions"
                    value={form.actions}
                    onChange={handleActionsChange}
                    variant="outlined"
                    renderValue={(selected) => (
                      <Stack direction="row" gap={1}>{selected.map((action) => <Chip key={action} label={action} />)}</Stack>
                    )}
                  >
                    <MenuItem value="view">View</MenuItem>
                    <MenuItem value="edit">Edit</MenuItem>
                    <MenuItem value="delete">Delete</MenuItem>
                    {/* Add more actions as needed */}
                  </Select>
                </FormControl>
                {error && <Typography color="error">{error}</Typography>}
                {success && <Typography color="success.main">{success}</Typography>}
                <Button type="submit" variant="contained" color="primary" disabled={loading}>
                  {loading ? <CircularProgress size={20} /> : 'Add User'}
                </Button>
              </Stack>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
