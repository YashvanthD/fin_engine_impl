import React, { useState } from 'react';
import { TextField, Button, MenuItem, Select, InputLabel, FormControl, Typography, Stack, InputAdornment } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';

const initialState = {
  title: '', // *
  description: '',
  status: 'pending',
  priority: 'normal',
  assigned_to: '', // *
  end_date: '', // *
  task_date: '',
  notes: '',
};

export default function TaskForm({ onCreate, onSearch }) {
  const [form, setForm] = useState(initialState);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  function handleChange(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleSearchChange(e) {
    setSearch(e.target.value);
    if (onSearch) onSearch(e.target.value);
  }

  function handleSubmit(e) {
    e.preventDefault();
    setError('');
    if (!form.title || !form.assigned_to || !form.end_date) {
      setError('Fields marked * are required');
      return;
    }
    onCreate(form);
    setForm(initialState);
  }

  return (
    <>
      <form onSubmit={handleSubmit} style={{marginTop:32}}>
        <Typography variant="h6" gutterBottom>Create Task</Typography>
        <Stack spacing={2}>
          <TextField label="Title *" name="title" value={form.title} onChange={handleChange} required fullWidth />
          <TextField label="Description" name="description" value={form.description} onChange={handleChange} multiline rows={2} fullWidth />
          <FormControl fullWidth>
            <InputLabel>Status</InputLabel>
            <Select name="status" value={form.status} label="Status" onChange={handleChange} variant="outlined">
              <MenuItem value="pending">Pending</MenuItem>
              <MenuItem value="inprogress">In Progress</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
            </Select>
          </FormControl>
          <FormControl fullWidth>
            <InputLabel>Priority</InputLabel>
            <Select name="priority" value={form.priority} label="Priority" onChange={handleChange} variant="outlined">
              <MenuItem value="low">Low</MenuItem>
              <MenuItem value="normal">Normal</MenuItem>
              <MenuItem value="high">High</MenuItem>
            </Select>
          </FormControl>
          <TextField label="Assigned To (User Key) *" name="assigned_to" value={form.assigned_to} onChange={handleChange} required fullWidth />
          <TextField label="End Date (YYYY-MM-DD) *" name="end_date" value={form.end_date} onChange={handleChange} required fullWidth />
          <TextField label="Task Date (YYYY-MM-DD)" name="task_date" value={form.task_date} onChange={handleChange} fullWidth />
          <TextField label="Notes" name="notes" value={form.notes} onChange={handleChange} multiline rows={2} fullWidth />
          {error && <Typography color="error">{error}</Typography>}
          <Button type="submit" variant="contained" color="primary">Create Task</Button>
        </Stack>
      </form>
      <TextField
        label="Search Task by ID or Keyword"
        value={search}
        onChange={handleSearchChange}
        fullWidth
        size="small"
        sx={{mt:2}}
        InputProps={{
          endAdornment: (
            <InputAdornment position="end">
              <SearchIcon />
            </InputAdornment>
          )
        }}
      />
    </>
  );
}
