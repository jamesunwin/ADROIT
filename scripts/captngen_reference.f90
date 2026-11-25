! Thin caller of the pinned upstream Capt'n Oper; no capture equations here.
! u0 is its RMS speed: sqrt(3/2)*ADROIT v0. The 2000 km/s cutoff is
! effectively untruncated for this comparison, avoiding the differing cut conventions.
program reference
  implicit none
  character(len=300) :: solar
  integer :: op, k, spin
  integer :: operators(5) = [1,4,6,8,11]
  double precision :: cp, cn, value, mass, capped, general
  call get_command_argument(1,solar)
  call captn_init(solar,0.3d0,220.d0,269.4438717061496d0,2000.d0)
  call captn_init_oper()
  mass=100.d0
  cp=1.d-8
  do k=1,5
    op=operators(k)
    cn=cp
    if (op.eq.4.or.op.eq.6) cn=0.d0
    call populate_array(cp+cn,op,0)
    call populate_array(cp-cn,op,1)
    call captn_oper(mass,0.5d0,16,capped)
    write(*,'(A,I3,ES24.15)') 'RESULT ',op,capped
    call populate_array(0.d0,op,0)
    call populate_array(0.d0,op,1)
  end do
  do spin=0,1
    call captn_general(mass,1.d-40,29,0,0,spin,general)
    write(*,'(A,I3,ES24.15)') 'GENERAL ',spin,general
  end do
end program reference
